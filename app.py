import sys
import types
# Fix for pydub error in Streamlit Cloud
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
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips, CompositeAudioClip

# Page configuration
st.set_page_config(page_title="Web (1): AI Burmese Movie Narrator Pro (Improved)", layout="wide")

st.title("🎬 Web (1): AI Burmese Movie Narrator Pro")
st.markdown("Video ကိုကြည့်ပြီး မူရင်းနောက်ခံစကားပြောများကို မြန်မာလို ကွတ်တိပြန်ပြောပေးသော AI စနစ်")

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
    # Using ThihaNeural for a clear male voice
    # Adding slight rate adjustment for more natural flow if needed
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="+0%")
    await communicate.save(output_path)

def parse_timestamps(ai_response):
    """
    Parses JSON from AI response to get segments with start, end, and text.
    Expected format from AI: [{"start": 0.0, "end": 5.0, "text": "..."}]
    """
    try:
        # Extract JSON block from markdown if present
        json_match = re.search(r'\[\s*{.*}\s*\]', ai_response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return []
    except Exception:
        return []

if video_path and api_key:
    if st.button("Generate Sync Dubbing"):
        with st.spinner("AI က Video ကို လေ့လာပြီး မူရင်းစကားပြောများကို ဘာသာပြန်နေပါတယ်..."):
            try:
                genai.configure(api_key=api_key)
                
                # Using latest Gemini models
                model = genai.GenerativeModel("gemini-1.5-pro") # Pro is better for complex timestamping
                
                # Upload video to Gemini
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(5)
                    video_file_ai = genai.get_file(video_file_ai.name)

                if video_file_ai.state.name == "FAILED":
                    st.error("Video processing failed.")
                    st.stop()

                prompt = """
                Task: Translate the ORIGINAL narration/dialogue of this video into BURMESE.
                
                Strict Rules:
                1. DO NOT add any extra commentary (e.g., "This movie is about...", "Hello everyone").
                2. Translate ONLY the actual spoken words or narration in the video.
                3. Use a professional, engaging, and natural Burmese male storytelling tone.
                4. Provide the output in a JSON array format with timestamps (seconds).
                
                Output Format:
                [
                  {"start": 0.0, "end": 3.5, "text": "မြန်မာလို ပြန်ဆိုချက် ၁"},
                  {"start": 4.0, "end": 8.0, "text": "မြန်မာလို ပြန်ဆိုချက် ၂"}
                ]
                
                Ensure the timestamps are accurate to the video content.
                """
                
                response = model.generate_content([video_file_ai, prompt])
                segments = parse_timestamps(response.text)
                
                if not segments:
                    st.error("AI ဆီကနေ အချိန်မှတ်တမ်းနဲ့ စာသားတွေကို မှန်ကန်စွာ မရရှိခဲ့ပါ။ ပြန်လည်ကြိုးစားကြည့်ပါ။")
                    st.write("Raw AI Response:", response.text)
                    st.stop()

                st.info(f"✅ AI က စုစုပေါင်း အပိုင်း {len(segments)} ပိုင်း ရှာဖွေတွေ့ရှိပါတယ်။")

                # Process Dubbing
                final_clips = []
                current_time = 0
                original_video = VideoFileClip(video_path)

                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, seg in enumerate(segments):
                    start = seg['start']
                    end = seg['end']
                    text = seg['text']
                    
                    status_text.text(f"Processing segment {i+1}/{len(segments)}: {text}")
                    
                    # 1. Add gap before segment if needed (original audio/video)
                    if start > current_time:
                        gap_clip = original_video.subclip(current_time, start).without_audio()
                        final_clips.append(gap_clip)
                    
                    # 2. Generate Audio for this segment
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                        asyncio.run(generate_speech(text, tmp_audio.name))
                        seg_audio = AudioFileClip(tmp_audio.name)
                    
                    # 3. Get the video segment
                    seg_video = original_video.subclip(start, end).without_audio()
                    
                    # 4. Handle Sync: If audio is longer than video segment
                    if seg_audio.duration > seg_video.duration:
                        # Freeze the last frame of the segment to match audio duration
                        last_frame = seg_video.get_frame(seg_video.duration - 0.01)
                        freeze_duration = seg_audio.duration - seg_video.duration
                        freeze_clip = ImageClip(last_frame).set_duration(freeze_duration)
                        seg_video_extended = concatenate_videoclips([seg_video, freeze_clip])
                        seg_video_final = seg_video_extended.set_audio(seg_audio)
                    else:
                        # Audio fits or is shorter, just set it
                        seg_video_final = seg_video.set_audio(seg_audio)
                    
                    final_clips.append(seg_video_final)
                    current_time = end
                    progress_bar.progress((i + 1) / len(segments))

                # Add remaining part of video if any
                if current_time < original_video.duration:
                    final_clips.append(original_video.subclip(current_time, original_video.duration).without_audio())

                # Combine all segments
                with st.spinner("Final Video ကို ပေါင်းစပ်နေပါတယ်..."):
                    final_video = concatenate_videoclips(final_clips)
                    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24)

                st.success("✅ အောင်မြင်စွာ လုပ်ဆောင်ပြီးပါပြီ!")
                st.video(output_path)
                
                with open(output_path, "rb") as f:
                    st.download_button("⬇️ Download Dubbed Video", f, "dubbed_movie.mp4", "video/mp4")

                # Cleanup
                original_video.close()
                genai.delete_file(video_file_ai.name)

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.exception(e)
            finally:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)

elif not api_key and video_path:
    st.warning("⚠️ Please enter your API Key in the sidebar.")
