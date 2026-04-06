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
from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips

# Page configuration
st.set_page_config(page_title="Web (1): AI Burmese Movie Narrator Pro", layout="wide")

st.title("🎬 Web (1): AI Burmese Movie Narrator Pro")
st.markdown("Video ကိုကြည့်ပြီး လူတစ်ယောက်က ဇာတ်ကြောင်းပြောပြနေသလို မြန်မာလို ရှင်းပြပေးသော AI စနစ်")

# Sidebar for Settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    st.info("API Key မရှိသေးရင် VPN ဖွင့်ပြီး [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

# Input Section - Video Upload ONLY (YouTube Link Removed)
st.subheader("📁 Upload Video")
video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])

video_path = None
if video_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
        tmp_video.write(video_file.read())
        video_path = tmp_video.name
    st.video(video_path)

async def generate_speech(text, output_path):
    # Using ThihaNeural for natural Burmese narration
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural")
    await communicate.save(output_path)

if video_path and api_key:
    if st.button("Generate Movie Recap"):
        with st.spinner("AI က Video ကိုကြည့်ပြီး ဇာတ်ကြောင်းပြောရန် ပြင်ဆင်နေပါတယ်..."):
            try:
                genai.configure(api_key=api_key)
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                
                model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
                
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file_ai = genai.get_file(video_file_ai.name)
                
                # Enhanced prompt for human-like storytelling
                prompt = """
                Analyze this video and provide a detailed movie recap in BURMESE language.
                
                STORYTELLING STYLE:
                - Act as a professional human movie narrator.
                - Use natural, engaging, and emotional Burmese storytelling style.
                - Avoid robotic or formal language. Use words that a real person would use to explain a movie to a friend.
                - Ensure the narration is clear and well-paced.
                
                OUTPUT FORMAT:
                [TITLES]
                Title 1
                Title 2
                Title 3
                [HASHTAGS]
                #tag1 #tag2 #tag3
                [RECAP]
                The detailed story...
                """
                
                response = model.generate_content([video_file_ai, prompt])
                
                if not response.candidates:
                    st.error("AI က ဒီ Video ကို ပိတ်ပင်ထားပါတယ် (Blocked)။")
                else:
                    full_text = response.text
                    
                    # Parsing titles and hashtags
                    titles_match = re.search(r'\[TITLES\]\n(.*?)\n(.*?)\n(.*?)\n', full_text + "\n\n\n", re.DOTALL)
                    hashtags_match = re.search(r'\[HASHTAGS\]\n(.*?)\n', full_text)
                    recap_text = full_text.split("[RECAP]")[-1].strip()
                    
                    # Display Social Media Box
                    st.success("✨ Social Media Ready Content!")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("📌 Catchy Titles")
                        if titles_match:
                            for i in range(1, 4):
                                st.code(titles_match.group(i).strip())
                    with col2:
                        st.subheader("🔥 Trending Hashtags")
                        if hashtags_match: st.code(hashtags_match.group(1).strip())
                    
                    st.subheader("📝 Full Recap Script:")
                    st.write(recap_text)
                    
                    # Generate Audio
                    audio_path = "narration.mp3"
                    asyncio.run(generate_speech(recap_text, audio_path))
                    
                    # Process Video
                    video_clip = VideoFileClip(video_path)
                    audio_clip = AudioFileClip(audio_path)
                    
                    # Mute original audio
                    video_muted = video_clip.without_audio()
                    
                    # Sync video duration with audio
                    if audio_clip.duration > video_muted.duration:
                        last_frame = video_muted.get_frame(video_muted.duration - 0.1)
                        freeze_frame = ImageClip(last_frame).with_duration(audio_clip.duration - video_muted.duration)
                        video_final = concatenate_videoclips([video_muted, freeze_frame])
                    else:
                        video_final = video_muted.with_duration(audio_clip.duration)
                    
                    final_video = video_final.with_audio(audio_clip)
                    
                    output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                    # MoviePy v2.0+ fix: remove verbose and logger
                    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True)
                    
                    st.success("✅ Video Processing Complete!")
                    st.video(output_video_path)
                    with open(output_video_path, "rb") as f:
                        st.download_button("⬇️ Download Final Video (MP4)", f, "my_movie_recap.mp4", "video/mp4")
                    
                    video_clip.close()
                    video_muted.close()
                
                genai.delete_file(video_file_ai.name)
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
elif not api_key and video_path:
    st.warning("⚠️ Please enter your API Key in the sidebar.")
