import sys
import types
# Fix for pydub error in Streamlit Cloud
sys.modules['pyaudioop'] = types.ModuleType('pyaudioop')

import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import tempfile
import time
from moviepy import VideoFileClip, AudioFileClip
from pytubefix import YouTube

# Page configuration
st.set_page_config(page_title="AI Burmese Movie Recap (YouTube & Video)", layout="wide")

st.title("🎬 AI Burmese Movie Recap")
st.markdown("YouTube Link သို့မဟုတ် Video တင်လိုက်ရုံနဲ့ **မြန်မာနောက်ခံစကားပြောပါတဲ့ Video အသစ်** ကို အလိုအလျောက် ဖန်တီးပေးပါတယ်။")

# Sidebar for API Key
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Enter Gemini API Key:", type="password")
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
    if st.button("Generate Burmese Recap Video"):
        with st.spinner("AI က Video ကို သေချာကြည့်ပြီး မြန်မာလို Recap Script ရေးနေပါတယ်..."):
            try:
                # 1. Configure AI and Find Model
                genai.configure(api_key=api_key)
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name)
                
                # 2. Upload Video to Gemini
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file_ai = genai.get_file(video_file_ai.name)
                
                # 3. Generate Script
                prompt = """
                Analyze this video carefully. 
                Write a professional, exciting movie recap script in BURMESE language based ONLY on the events happening in this video.
                STRICT RULES:
                1. Do NOT hallucinate. Only describe what is actually shown in the video.
                2. Use an engaging, storytelling tone (Movie Recap Style).
                3. Use natural, spoken Burmese (not formal book language).
                4. Start with a hook and end with a summary.
                5. Format the script for a male narrator.
                """
                response = model.generate_content([video_file_ai, prompt])
                recap_script = response.text
                
                st.subheader("Generated Script:")
                st.write(recap_script)
                
                # 4. Generate Audio
                voice = "my-MM-ThihaNeural"
                communicate = edge_tts.Communicate(recap_script, voice)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                    asyncio.run(communicate.save(tmp_audio.name))
                    audio_path = tmp_audio.name
                
                # 5. Combine Video and Audio
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_path)
                final_video = video_clip.with_audio(audio_clip)
                
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
                
                # 6. Display and Download
                st.success("မြန်မာနောက်ခံစကားပြောပါတဲ့ Video အသစ် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ!")
                st.video(output_video_path)
                with open(output_video_path, "rb") as f:
                    st.download_button("Download Final Video (MP4)", f, "my_movie_recap_final.mp4", "video/mp4")
                
                # Cleanup
                video_clip.close()
                audio_clip.close()
                genai.delete_file(video_file_ai.name)
                
            except Exception as e:
                st.error(f"Error: {e}")
elif not api_key and video_path:
    st.warning("Please enter your API Key in the sidebar.")
