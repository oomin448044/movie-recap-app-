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

st.title("🎬 Burmese AI Movie Narrator Pro")
st.info("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.markdown("[Get API Key here](https://aistudio.google.com/app/apikey)")

# --- Functions ---
async def generate_burmese_audio(text, output_path):
    # rate="-15%" က အသံကို ပိုနှေးစေပြီး AI အသံထက် လူပြောသံနဲ့ ပိုတူစေပါတယ်
    # pitch="-5Hz" က အသံကို နည်းနည်းလေး ပိုလေးစေပါတယ်
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-15%", pitch="-5Hz")
    await communicate.save(output_path)

def blur_original_subtitles(image):
    h, w, _ = image.shape
    bottom_h = int(h * 0.15)
    bottom_part = image[h-bottom_h:h, 0:w]
    blurred_bottom = cv2.GaussianBlur(bottom_part, (51, 51), 0)
    image[h-bottom_h:h, 0:w] = blurred_bottom
    return image

# --- Main App ---
video_file = st.file_uploader("📁 Upload Movie Clip:", type=["mp4", "mov", "avi"])

if video_file and api_key:
    # Save uploaded file with proper extension to avoid mime_type error
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
        tfile.write(video_file.read())
        video_path = tfile.name

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            with st.status("AI is processing...", expanded=True) as status:
                st.write("📤 Uploading video to AI...")
                # mime_type ကို အသေ သတ်မှတ်ပေးလိုက်ခြင်းဖြင့် error ကို ဖြေရှင်းပါတယ်
                gen_file = genai.upload_file(path=video_path, mime_type="video/mp4")
                
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                st.write("📝 Generating natural Burmese script...")
                prompt = """
                Analyze this movie clip and write a professional movie recap in BURMESE.
                STYLE: Natural, engaging, storytelling. Like a friend telling a story.
                Use 'ကျွန်တော်တို့' or 'သူက' instead of formal words.
                FORMAT:
                [TITLES]
                (3 catchy titles)
                [RECAP]
                (Full story)
                """
                response = model.generate_content([gen_file, prompt])
                full_response = response.text

                # Parse Titles and Recap
                titles = re.findall(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_text = re.findall(r"\[RECAP\](.*)", full_response, re.DOTALL)[0].strip() if "[RECAP]" in full_response else full_response

                st.write("🎙️ Creating natural voiceover (Male Voice)...")
                audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                asyncio.run(generate_burmese_audio(recap_text, audio_temp.name))

                st.write("🎬 Finalizing Video & Audio Sync...")
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_temp.name)

                video_processed = video_clip.fl_image(blur_original_subtitles).without_audio()

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
                
                status.update(label="✅ Complete!", state="complete")

            st.success("✨ Ready!")
            st.video(output_video.name)
            
            # Cleanup
            video_clip.close()
            audio_clip.close()
            os.remove(audio_temp.name)
            genai.delete_file(gen_file.name)

        except Exception as e:
            st.error(f"Error: {e}")
