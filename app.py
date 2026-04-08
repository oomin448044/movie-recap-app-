import sys
import types
# Fix for pydub/pyaudio error in Streamlit Cloud
sys.modules["pyaudioop"] = types.ModuleType("pyaudioop")

import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import tempfile
import time
import re
import json
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips

# Page configuration
st.set_page_config(page_title="AI Burmese Movie Narrator Pro", layout="wide")

st.title("🎬 AI Burmese Movie Narrator Pro")
st.markdown("မူရင်းနောက်ခံစကားပြောများကို မြန်မာလို ကွတ်တိပြန်ပြောပေးသော AI စနစ်")

# Sidebar for Settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.info("API Key မရှိသေးရင် [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

# Input Section - Video Upload
st.subheader("📁 Upload Video")
video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])

video_path = None
if video_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
        tmp_video.write(video_file.read())
        video_path = tmp_video.name
    st.video(video_path)

async def generate_speech(text, output_path):
    # ThihaNeural for a clear male storyteller voice
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-5%")
    await communicate.save(output_path)

def extract_json(text):
    """Robustly extracts JSON array from AI response."""
    try:
        match = re.search(r'\[\s*{.*}\s*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
    except:
        return None

if video_path and api_key:
    if st.button("Generate Sync Dubbing"):
        with st.spinner("AI က Video ကို လေ့လာပြီး မူရင်းစကားပြောများကို ဘာသာပြန်နေပါတယ်..."):
            try:
                genai.configure(api_key=api_key)
                
                # GET AVAILABLE MODELS
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                
                # Priority list: Use 1.5-flash first as it has better quota availability for free tier
                model = None
                model_name_used = ""
                priority_list = ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-1.0-pro"]
                
                for p_model in priority_list:
                    if p_model in available_models:
                        model = genai.GenerativeModel(p_model)
                        model_name_used = p_model
                        break
                
                if not model and available_models:
                    model = genai.GenerativeModel(available_models[0])
                    model_name_used = available_models[0]

                if not model:
                    st.error("❌ သင့် API Key နဲ့ အသုံးပြုလို့ရတဲ့ Gemini Model တစ်ခုမှ ရှာမတွေ့ပါ။")
                    st.stop()
                else:
                    st.info(f"✅ Using Gemini Model: {model_name_used}")

                # Upload video to Gemini
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(5)
                    video_file_ai = genai.get_file(video_file_ai.name)

                if video_file_ai.state.name == "FAILED":
                    st.error("Video processing failed.")
                    st.stop()

                # Strict prompt to avoid extra commentary
                prompt = """
                Analyze the original narration/dialogue in this video. 
                Translate it into BURMESE language.
                
                STRICT RULES:
                1. DO NOT add any extra commentary (NO "This movie is about...", NO "Hello everyone").
                2. ONLY translate the actual spoken words or narration from the video.
                3. Use a natural, professional, and clear Burmese male storytelling tone.
                4. Output MUST be a JSON array of objects with 'start', 'end', and 'text' keys.
                
                Output Format Example:
                [
                  {"start": 0.0, "end": 3.0, "text": "မြန်မာလို ပြန်ဆိုချက် ၁"},
                  {"start": 3.5, "end": 7.0, "text": "မြန်မာလို ပြန်ဆိုချက် ၂"}
                ]
                """
                
                response = model.generate_content([video_file_ai, prompt])
                segments = extract_json(response.text)
                
                if not segments:
                    st.error("AI ဆီကနေ အချိန်မှတ်တမ်းနဲ့ စာသားတွေကို မှန်ကန်စွာ မရရှိခဲ့ပါ။")
                    st.text(response.text)
                    st.stop()

                st.info(f"✅ AI က စုစုပေါင်း အပိုင်း {len(segments)} ပိုင်း ရှာဖွေတွေ့ရှိပါတယ်။")

                # Processing video and audio segments
                final_clips = []
                current_time = 0
                original_video = VideoFileClip(video_path)
                
                progress_bar = st.progress(0)

                for i, seg in enumerate(segments):
                    start = float(seg['start'])
                    end = float(seg['end'])
                    text = seg['text']
                    
                    if start > current_time:
                        gap_clip = original_video.subclip(current_time, start).without_audio()
                        final_clips.append(gap_clip)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                        asyncio.run(generate_speech(text, tmp_audio.name))
                        seg_audio = AudioFileClip(tmp_audio.name)
                    
                    seg_video = original_video.subclip(start, end).without_audio()
                    
                    if seg_audio.duration > seg_video.duration:
                        last_frame = seg_video.get_frame(seg_video.duration - 0.01)
                        freeze_duration = seg_audio.duration - seg_video.duration
                        freeze_clip = ImageClip(last_frame).set_duration(freeze_duration)
                        seg_video_extended = concatenate_videoclips([seg_video, freeze_clip])
                        seg_video_final = seg_video_extended.set_audio(seg_audio)
                    else:
                        seg_video_final = seg_video.set_audio(seg_audio)
                    
                    final_clips.append(seg_video_final)
                    current_time = end
                    progress_bar.progress((i + 1) / len(segments))

                if current_time < original_video.duration:
                    final_clips.append(original_video.subclip(current_time, original_video.duration).without_audio())

                with st.spinner("Final Video ကို ပေါင်းစပ်နေပါတယ်..."):
                    final_video = concatenate_videoclips(final_clips)
                    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24)

                st.success("✅ အောင်မြင်စွာ လုပ်ဆောင်ပြီးပါပြီ!")
                st.video(output_path)
                with open(output_path, "rb") as f:
                    st.download_button("⬇️ Download Final Video", f, "dubbed_video.mp4", "video/mp4")

                original_video.close()
                genai.delete_file(video_file_ai.name)

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
            finally:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)

elif not api_key and video_path:
    st.warning("⚠️ Please enter your API Key in the sidebar.")
