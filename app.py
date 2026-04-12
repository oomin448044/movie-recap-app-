import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import tempfile
import time
import re
import cv2
import numpy as np
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip

# --- Configuration ---
st.set_page_config(page_title="Burmese AI Movie Narrator Pro", layout="wide")

st.title("🎬 Burmese AI Movie Narrator Pro")
st.info("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.markdown("[Get API Key here](https://aistudio.google.com/app/apikey)")

# --- Functions ---
async def generate_burmese_audio(text, output_path):
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-5%", pitch="-2Hz")
    await communicate.save(output_path)

def find_working_model():
    try:
        models = genai.list_models()
        for m in models:
            if 'generateContent' in m.supported_generation_methods and 'flash' in m.name:
                return m.name
        return 'models/gemini-1.5-flash'
    except Exception:
        return 'models/gemini-1.5-flash'

# --- Main App ---
video_file = st.file_uploader("📁 Upload Movie Clip:", type=["mp4", "mov", "avi"])

if video_file and api_key:
    # Temporary file creation with proper closing before usage
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tfile.write(video_file.read())
    video_path = tfile.name
    tfile.close() # ဖိုင်ကို အရင်ပိတ်မှ MoviePy က ကောင်းကောင်းဖတ်နိုင်မှာပါ

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            
            with st.status("AI is processing...", expanded=True) as status:
                st.write("🔍 Finding best available Gemini model...")
                model_name = find_working_model()
                model = genai.GenerativeModel(model_name)

                st.write("📤 Uploading video to AI...")
                gen_file = genai.upload_file(path=video_path, mime_type="video/mp4")
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                st.write("📝 Generating natural Burmese narration...")
                prompt = """
                Analyze this movie clip and provide a BURMESE narration.
                STRICT RULES:
                1. Translate and narrate only what is happening in the video.
                2. NO introductions and NO conclusions.
                3. STYLE: Act like a professional human storyteller. 
                4. TONE: Conversational, emotional, and engaging.
                5. Use natural Burmese spoken language.
                FORMAT:
                [TITLES]
                (3 catchy titles)
                [RECAP]
                (The narration text only)
                """
                
                try:
                    response = model.generate_content([gen_file, prompt])
                except Exception as e:
                    if "429" in str(e):
                        st.warning("⚠️ Quota limit reached. Retrying in 20 seconds...")
                        time.sleep(20)
                        response = model.generate_content([gen_file, prompt])
                    else: raise e

                full_response = response.text
                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                asyncio.run(generate_burmese_audio(recap_text, audio_temp_path))

                st.write("🎬 Finalizing Video & Audio Sync...")
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_temp_path)
                video_muted = video_clip.without_audio()

                # Sync logic: အသံက ပိုရှည်နေလျှင် နောက်ဆုံး Frame ကို Freeze လုပ်ပါမည်
                if audio_clip.duration > video_muted.duration:
                    freeze_duration = audio_clip.duration - video_muted.duration
                    last_frame = video_muted.get_frame(video_muted.duration - 0.01)
                    freeze_clip = ImageClip(last_frame).set_duration(freeze_duration).set_start(video_muted.duration)
                    video_final = CompositeVideoClip([video_muted, freeze_clip]).set_duration(audio_clip.duration)
                else:
                    video_final = video_muted.subclip(0, audio_clip.duration)

                final_result = video_final.set_audio(audio_clip)
                
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                final_result.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=24)
                
                status.update(label="✅ Complete!", state="complete")

            st.success("✨ Your Movie Recap is Ready!")
            st.video(output_video_path)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📌 Social Media Titles")
                for t in title_list[:3]:
                    if t.strip(): st.code(t.strip(), language="text")
            
            with col2:
                st.subheader("📥 Download")
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Final Video", f, file_name="burmese_movie_recap.mp4")

            # Cleanup
            video_clip.close()
            audio_clip.close()
            if os.path.exists(audio_temp_path): os.remove(audio_temp_path)
            if os.path.exists(output_video_path): os.remove(output_video_path)
            genai.delete_file(gen_file.name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            if os.path.exists(video_path): os.remove(video_path)
