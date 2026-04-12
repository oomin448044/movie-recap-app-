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
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-15%", pitch="-5Hz")
    await communicate.save(output_path)

def blur_original_subtitles(image):
    h, w, _ = image.shape
    bottom_h = int(h * 0.15)
    bottom_part = image[h-bottom_h:h, 0:w]
    blurred_bottom = cv2.GaussianBlur(bottom_part, (51, 51), 0)
    image[h-bottom_h:h, 0:w] = blurred_bottom
    return image

def optimize_video_for_ai(input_path, output_path):
    """Gemini API Quota သက်သာစေရန် Video Resolution ကို လျှော့ချပေးသည့် Function"""
    cap = cv2.VideoCapture(input_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # AI အတွက် 480p က လုံလောက်ပါတယ် (Token သက်သာစေပါတယ်)
    target_height = 480
    target_width = int(width * (target_height / height))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        resized_frame = cv2.resize(frame, (target_width, target_height))
        out.write(resized_frame)
        
    cap.release()
    out.release()

# --- Main App ---
video_file = st.file_uploader("📁 Upload Movie Clip:", type=["mp4", "mov", "avi"])

if video_file and api_key:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
        tfile.write(video_file.read())
        video_path = tfile.name

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            
            with st.status("AI is processing...", expanded=True) as status:
                # 1. Video Optimization
                st.write("⚙️ Optimizing video for AI (Reducing tokens)...")
                optimized_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                optimize_video_for_ai(video_path, optimized_path)

                # 2. Upload Video
                st.write("📤 Uploading video to AI...")
                gen_file = genai.upload_file(path=optimized_path, mime_type="video/mp4")
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                # 3. Generate Script (Using stable model first to avoid quota issues)
                st.write("📝 Generating natural Burmese storytelling script...")
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = """
                Analyze this movie clip and write a professional movie recap in BURMESE.
                STYLE: Natural, engaging, human-like storytelling. 
                FORMAT:
                [TITLES]
                (Give 3 catchy titles)
                [RECAP]
                (The full story in Burmese)
                """
                
                # Quota Error ဖြစ်ခဲ့ရင် ၅ စက္ကန့်စောင့်ပြီး တစ်ခါ ပြန်ကြိုးစားပါမယ်
                try:
                    response = model.generate_content([gen_file, prompt])
                except Exception as e:
                    if "429" in str(e):
                        st.warning("⚠️ Quota limit reached. Retrying in 10 seconds...")
                        time.sleep(10)
                        response = model.generate_content([gen_file, prompt])
                    else: raise e

                full_response = response.text

                # Parsing
                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                # 4. Generate Audio
                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                asyncio.run(generate_burmese_audio(recap_text, audio_temp.name))

                # 5. Video Processing
                st.write("🎬 Finalizing Video & Audio Sync...")
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_temp.name)

                video_processed = video_clip.fl_image(blur_original_subtitles).without_audio()

                if audio_clip.duration > video_processed.duration:
                    freeze_duration = audio_clip.duration - video_processed.duration
                    last_frame = video_processed.get_frame(video_processed.duration - 0.1)
                    freeze_clip = ImageClip(last_frame).set_duration(freeze_duration)
                    video_final = concatenate_videoclips([video_processed, freeze_clip])
                else:
                    video_final = video_processed.subclip(0, audio_clip.duration)

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
            os.remove(audio_temp.name)
            os.remove(optimized_path)
            genai.delete_file(gen_file.name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
