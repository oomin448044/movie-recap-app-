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
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips, TextClip, CompositeVideoClip

# --- Configuration ---
st.set_page_config(page_title="Burmese AI Movie Narrator Pro", layout="wide")

# Custom CSS for better UI
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stDownloadButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .copy-box { padding: 10px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🎬 Burmese AI Movie Narrator Pro")
st.info("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.markdown("[Get API Key here](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    st.write("🛠️ **Features:**")
    st.write("- ✅ Remove Original Audio")
    st.write("- ✅ Natural Burmese Male AI Voice")
    st.write("- ✅ Auto-Sync Video with Narration")
    st.write("- ✅ 3 Catchy Titles for Social Media")

# --- Functions ---
async def generate_burmese_audio(text, output_path):
    """Generates natural Burmese male voice using edge-tts"""
    # 'my-MM-ThihaNeural' is the best male voice for storytelling
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="+0%")
    await communicate.save(output_path)

def blur_original_subtitles(image):
    """Blurs the bottom part of the video to hide original subtitles"""
    h, w, _ = image.shape
    bottom_h = int(h * 0.15) # Blur bottom 15%
    bottom_part = image[h-bottom_h:h, 0:w]
    blurred_bottom = cv2.GaussianBlur(bottom_part, (51, 51), 0)
    image[h-bottom_h:h, 0:w] = blurred_bottom
    return image

# --- Main App ---
video_file = st.file_uploader("📁 Upload Movie Clip (mp4, mov, avi):", type=["mp4", "mov", "avi"])

if video_file and api_key:
    # Save uploaded file to temp
    tfile = tempfile.NamedTemporaryFile(delete=False)
    tfile.write(video_file.read())
    video_path = tfile.name

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash') # Using stable 1.5 flash

            with st.status("AI is analyzing the video...", expanded=True) as status:
                # 1. Upload to Gemini
                st.write("📤 Uploading video to AI...")
                gen_file = genai.upload_file(path=video_path)
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                # 2. Generate Script
                st.write("📝 Generating Burmese storytelling script...")
                prompt = """
                Analyze this movie clip and write a professional movie recap in BURMESE.
                STYLE: Natural, engaging, human-like storytelling (NOT formal).
                VOICE: Imagine a male narrator telling a story to friends.
                FORMAT:
                [TITLES]
                (Give 3 catchy titles)
                [RECAP]
                (The full story in Burmese)
                """
                response = model.generate_content([gen_file, prompt])
                full_response = response.text

                # Parse Titles and Recap
                titles = re.findall(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap = re.findall(r"\[RECAP\](.*)", full_response, re.DOTALL)
                
                title_list = titles[0].strip().split('\n') if titles else ["Movie Recap 1", "Movie Recap 2", "Movie Recap 3"]
                recap_text = recap[0].strip() if recap else full_response

                # 3. Generate Audio
                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                asyncio.run(generate_burmese_audio(recap_text, audio_temp.name))

                # 4. Video Processing (Sync & Mute)
                st.write("🎬 Syncing video with new audio...")
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_temp.name)

                # Mute original & Blur subtitles
                video_processed = video_clip.fl_image(blur_original_subtitles).without_audio()

                # Sync logic: If audio is longer, freeze the last frame
                if audio_clip.duration > video_processed.duration:
                    freeze_duration = audio_clip.duration - video_processed.duration
                    last_frame = video_processed.get_frame(video_processed.duration - 0.1)
                    freeze_clip = ImageClip(last_frame).set_duration(freeze_duration)
                    final_video_clip = concatenate_videoclips([video_processed, freeze_clip])
                else:
                    final_video_clip = video_processed.subclip(0, audio_clip.duration)

                final_video_clip = final_video_clip.set_audio(audio_clip)
                
                output_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                final_video_clip.write_videofile(output_video.name, codec="libx264", audio_codec="aac", fps=24)
                
                status.update(label="✅ Process Complete!", state="complete", expanded=False)

            # --- Results ---
            st.success("✨ Your Movie Recap is Ready!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📌 Social Media Titles")
                for i, t in enumerate(title_list[:3]):
                    if t.strip():
                        st.code(t.strip(), language="text")
            
            with col2:
                st.subheader("📥 Download Video")
                with open(output_video.name, "rb") as f:
                    st.download_button("Download Final Video", f, file_name="burmese_movie_recap.mp4")

            st.video(output_video.name)

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

st.divider()
st.caption("Developed by AI Developer for Burmese Movie Lovers")
