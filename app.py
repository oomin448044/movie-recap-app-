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
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips

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
    # အသံကို ပိုနှေးစေပြီး AI အသံထက် လူပြောသံနဲ့ ပိုတူစေရန် ညှိထားပါသည်
    # rate="-15%" က အေးအေးဆေးဆေး ဇာတ်လမ်းပြောပြနေသလို ဖြစ်စေပါတယ်
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-15%", pitch="-5Hz")
    await communicate.save(output_path)

def blur_original_subtitles(image):
    """မူရင်းစာတန်းထိုးများကို ဖုံးကွယ်ရန် Video ၏ အောက်ခြေကို Blur လုပ်ပေးပါသည်"""
    h, w, _ = image.shape
    bottom_h = int(h * 0.15)
    bottom_part = image[h-bottom_h:h, 0:w]
    blurred_bottom = cv2.GaussianBlur(bottom_part, (51, 51), 0)
    image[h-bottom_h:h, 0:w] = blurred_bottom
    return image

def get_best_model():
    """အလုပ်လုပ်နိုင်မည့် အကောင်းဆုံး Gemini Model ကို အလိုအလျောက် ရှာဖွေပေးမည့် Function"""
    available_models = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
    for model_name in available_models:
        try:
            model = genai.GenerativeModel(model_name)
            return model, model_name
        except Exception:
            continue
    return None, None

# --- Main App ---
video_file = st.file_uploader("📁 Upload Movie Clip:", type=["mp4", "mov", "avi"])

if video_file and api_key:
    # Save uploaded file with .mp4 suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
        tfile.write(video_file.read())
        video_path = tfile.name

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            
            with st.status("AI is processing...", expanded=True) as status:
                # 1. Smart Model Selection
                st.write("🔍 Finding best available Gemini model...")
                model, used_model_name = get_best_model()
                if not model:
                    st.error("❌ No supported Gemini models found. Please check your API key.")
                    st.stop()
                st.write(f"✅ Using Model: {used_model_name}")

                # 2. Upload Video
                st.write("📤 Uploading video to AI...")
                gen_file = genai.upload_file(path=video_path, mime_type="video/mp4")
                
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                # 3. Generate Script
                st.write("📝 Generating natural Burmese storytelling script...")
                prompt = """
                Analyze this movie clip and write a professional movie recap in BURMESE.
                STYLE: Natural, engaging, human-like (NOT formal). 
                Act as a professional movie narrator talking to an audience.
                FORMAT:
                [TITLES]
                (Give 3 catchy titles)
                [RECAP]
                (The full story in Burmese)
                """
                response = model.generate_content([gen_file, prompt])
                full_response = response.text

                # Parse Titles and Recap
                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap 1", "Movie Recap 2", "Movie Recap 3"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                # 4. Generate Audio
                st.write("🎙️ Creating natural Burmese voiceover (Thiha Male Voice)...")
                audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                asyncio.run(generate_burmese_audio(recap_text, audio_temp.name))

                # 5. Video Processing
                st.write("🎬 Finalizing Video & Audio Sync...")
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_temp.name)

                # မူရင်းအသံဖျောက်ခြင်းနှင့် စာတန်းထိုးနေရာ Blur လုပ်ခြင်း
                video_processed = video_clip.fl_image(blur_original_subtitles).without_audio()

                # Sync logic: အသံက ပိုရှည်နေလျှင် နောက်ဆုံး Frame ကို ရပ်ထားပါမည်
                if audio_clip.duration > video_processed.duration:
                    freeze_duration = audio_clip.duration - video_processed.duration
                    last_frame = video_processed.get_frame(video_processed.duration - 0.1)
                    freeze_clip = ImageClip(last_frame).set_duration(freeze_duration)
                    final_video_clip = concatenate_videoclips([video_processed, freeze_clip])
                else:
                    final_video_clip = video_processed.subclip(0, audio_clip.duration)

                final_video_clip = final_video_clip.set_audio(audio_clip)
                
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                final_video_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=24)
                
                status.update(label="✅ Complete!", state="complete")

            # --- Results ---
            st.success("✨ Your Movie Recap is Ready!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📌 Social Media Titles")
                for t in title_list[:3]:
                    if t.strip():
                        st.code(t.strip(), language="text")
            
            with col2:
                st.subheader("📥 Download Video")
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Final Video", f, file_name="burmese_movie_recap.mp4")

            st.video(output_video_path)

            # Cleanup
            video_clip.close()
            audio_clip.close()
            os.remove(audio_temp.name)
            genai.delete_file(gen_file.name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.exception(e)

else:
    if not api_key:
        st.warning("⚠️ Please enter your Gemini API Key in the sidebar.")
    if not video_file:
        st.info("📂 Please upload a video file to start.")
