import sys
import types
# Fix for pydub error in Streamlit Cloud
sys.modules['pyaudioop'] = types.ModuleType('pyaudioop')

import streamlit as st
import google.generativeai as genai
from google.generativeai.types import SafetySettingDict, HarmCategory, HarmBlockThreshold
import os
import asyncio
import edge_tts
import tempfile
import time
from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip
from pytubefix import YouTube

# Page configuration
st.set_page_config(page_title="AI Burmese Movie Narrator", layout="wide")

st.title("🎬 AI Burmese Movie Narrator")
st.markdown("Video ပြကွက်တွေနဲ့ **ကွက်တိကျပြီး စိတ်လှုပ်ရှားစရာကောင်းတဲ့ မြန်မာနောက်ခံစကားပြော** ကို ဖန်တီးပေးပါတယ်။")

# Sidebar for Settings
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
    logo_file = st.file_uploader("Upload Channel Logo (PNG/JPG):", type=["png", "jpg", "jpeg"])
    st.info("API Key မရှိသေးရင် VPN ဖွင့်ပြီး [Google AI Studio](https://aistudio.google.com/app/apikey) မှာ ယူပါ။")

# Input Section
tab1, tab2 = st.tabs(["YouTube Link", "Video Upload"])

video_path = None

with tab1:
    youtube_url = st.text_input("Paste YouTube Link here:")
    if youtube_url:
        with st.spinner("Downloading YouTube video..."):
            try:
                yt = YouTube(youtube_url)
                stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
                video_path = stream.download(output_path=tempfile.gettempdir())
                st.video(video_path)
            except Exception as e:
                st.error(f"YouTube Download Error: {e}")

with tab2:
    video_file = st.file_uploader("Upload Video (Max 500MB):", type=["mp4", "mov", "avi"])
    if video_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            tmp_video.write(video_file.read())
            video_path = tmp_video.name
        st.video(video_path)

if video_path and api_key:
    if st.button("Generate Branded Narrated Video"):
        with st.spinner("AI က Video ကိုကြည့်ပြီး စိတ်လှုပ်ရှားစရာကောင်းတဲ့ ဇာတ်ကြောင်းပြောနေပါတယ်..."):
            try:
                # 1. Configure AI
                genai.configure(api_key=api_key)
                
                # Set Safety Settings to BLOCK_NONE to avoid PROHIBITED_CONTENT errors
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
                
                # 2. Upload Video to Gemini
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file_ai = genai.get_file(video_file_ai.name)
                
                # 3. Generate Engaging & Dramatic Script
                prompt = """
                Analyze this video carefully. 
                Act as a professional Movie Recap Narrator. 
                Tell the story of what is happening in this video in an EXCITING, DRAMATIC, and ENGAGING way in BURMESE language.
                
                STRICT RULES:
                1. NO introductions, NO greetings, NO commentary.
                2. Use natural, spoken Burmese with emotional depth.
                3. Do NOT be too brief or robotic. Make it sound like a real person telling a thrilling story.
                4. Ensure the narration flows well and matches the timing of the actions in the video.
                5. Output ONLY the Burmese storytelling text.
                """
                
                response = model.generate_content([video_file_ai, prompt])
                
                # Check if response was blocked
                if not response.candidates:
                    st.error("AI က ဒီ Video ထဲက အကြောင်းအရာတချို့ကို ပိတ်ပင်ထားပါတယ် (Blocked)။ ကျေးဇူးပြု၍ အခြား Video တစ်ခုနဲ့ ပြန်စမ်းကြည့်ပေးပါခင်ဗျာ။")
                else:
                    narrator_script = response.text
                    st.subheader("Generated Script:")
                    st.write(narrator_script)
                    
                    # 4. Generate Audio
                    voice = "my-MM-ThihaNeural"
                    communicate = edge_tts.Communicate(narrator_script, voice, rate="+5%", pitch="+0Hz")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                        asyncio.run(communicate.save(tmp_audio.name))
                        audio_path = tmp_audio.name
                    
                    # 5. Video Editing
                    video_clip = VideoFileClip(video_path)
                    audio_clip = AudioFileClip(audio_path)
                    
                    if audio_clip.duration > video_clip.duration:
                        audio_clip = audio_clip.subclipped(0, video_clip.duration)
                    
                    video_with_audio = video_clip.with_audio(audio_clip)
                    
                    if logo_file:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                            tmp_logo.write(logo_file.read())
                            logo_path = tmp_logo.name
                        logo = (ImageClip(logo_path)
                                .with_duration(video_clip.duration)
                                .resized(height=50) 
                                .with_position(("left", "top"))
                                .with_start(0))
                        final_video = CompositeVideoClip([video_with_audio, logo])
                    else:
                        final_video = video_with_audio
                    
                    output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True)
                    
                    # 6. Display and Download
                    st.success("စိတ်လှုပ်ရှားစရာကောင်းတဲ့ ဇာတ်ကြောင်းပြော Video ရပါပြီ!")
                    st.video(output_video_path)
                    with open(output_video_path, "rb") as f:
                        st.download_button("Download Final Video (MP4)", f, "my_movie_story.mp4", "video/mp4")
                    
                    # Cleanup
                    video_clip.close()
                    audio_clip.close()
                
                genai.delete_file(video_file_ai.name)
                
            except Exception as e:
                st.error(f"Error: {e}")
elif not api_key and video_path:
    st.warning("Please enter your API Key in the sidebar.")
