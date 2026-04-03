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
import re
import requests
from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, CompositeAudioClip, afx
from pytubefix import YouTube

# Page configuration
st.set_page_config(page_title="AI Burmese Movie Narrator Ultra", layout="wide")

st.title("🎬 AI Burmese Movie Narrator Ultra")
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

async def generate_voiceover(text, output_path):
    communicate = edge_tts.Communicate(text, "my-MM-ThihaNeural", rate="-5%", pitch="+0Hz")
    await communicate.save(output_path)

def get_bgm(genre):
    bgm_links = {
        "action": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "horror": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "drama": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
        "default": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"
    }
    url = bgm_links.get(genre.lower(), bgm_links["default"])
    try:
        r = requests.get(url, timeout=10)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(r.content)
            return f.name
    except:
        return None

if video_path and api_key:
    if st.button("Generate Branded Narrated Video"):
        with st.spinner("AI က Video ကိုကြည့်ပြီး စိတ်လှုပ်ရှားစရာကောင်းတဲ့ ဇာတ်ကြောင်းပြောနေပါတယ်..."):
            try:
                genai.configure(api_key=api_key)
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
                
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                model_name = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
                model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
                
                video_file_ai = genai.upload_file(path=video_path)
                while video_file_ai.state.name == "PROCESSING":
                    time.sleep(2)
                    video_file_ai = genai.get_file(video_file_ai.name)
                
                prompt = """
                Analyze this video carefully. Act as a professional Movie Recap Narrator.
                Tell the story of what is happening in an EXCITING, DRAMATIC, and ENGAGING way in BURMESE language.
                
                STRICT RULES:
                1. Use natural, spoken Burmese (Spoken Style).
                2. NO introductions, NO greetings, NO commentary.
                3. You MUST provide timestamps for each part of the story to match the video.
                4. Format: [start_time - end_time] Story text
                5. Also, identify the GENRE of this video (Action, Horror, Drama, or Sci-Fi) at the very first line.
                """
                
                response = model.generate_content([video_file_ai, prompt])
                
                if not response.candidates:
                    st.error("AI က ဒီ Video ကို ပိတ်ပင်ထားပါတယ် (Blocked)။")
                else:
                    narrator_script = response.text
                    st.subheader("Generated Script:")
                    st.write(narrator_script)
                    
                    lines = narrator_script.strip().split('\n')
                    genre = "default"
                    if lines[0].startswith("GENRE:"):
                        genre = lines[0].replace("GENRE:", "").strip()
                        lines = lines[1:]
                    
                    video_clip = VideoFileClip(video_path)
                    video_muted = video_clip.without_audio()
                    
                    audio_segments = []
                    video_segments = []
                    current_time = 0
                    
                    from moviepy import concatenate_videoclips
                    
                    for line in lines:
                        match = re.search(r'\[(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\]\s*(.*)', line)
                        if match:
                            start_str, end_str, text = match.groups()
                            start_sec = int(start_str.split(':')[0]) * 60 + int(start_str.split(':')[1])
                            end_sec = int(end_str.split(':')[0]) * 60 + int(end_str.split(':')[1])
                            
                            if text.strip():
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_audio:
                                    asyncio.run(generate_voiceover(text, tmp_audio.name))
                                    voice_audio = AudioFileClip(tmp_audio.name)
                                    
                                    scene_duration = end_sec - start_sec
                                    if voice_audio.duration > scene_duration:
                                        scene = video_muted.subclipped(start_sec, end_sec)
                                        last_frame = scene.get_frame(scene.duration - 0.01)
                                        freeze_duration = voice_audio.duration - scene_duration
                                        freeze_clip = ImageClip(last_frame).with_duration(freeze_duration)
                                        final_scene = concatenate_videoclips([scene, freeze_clip])
                                    else:
                                        final_scene = video_muted.subclipped(start_sec, end_sec)
                                    
                                    video_segments.append(final_scene)
                                    audio_segments.append(voice_audio.with_start(current_time))
                                    current_time += final_scene.duration
                    
                    if video_segments:
                        final_video_visual = concatenate_videoclips(video_segments)
                        voice_audio_combined = CompositeAudioClip(audio_segments)
                        
                        bgm_path = get_bgm(genre)
                        if bgm_path:
                            bgm_audio = AudioFileClip(bgm_path).with_volume_scaled(0.15)
                            # Correct way to loop audio in MoviePy v2.0+
                            bgm_audio = afx.audio_loop(bgm_audio, duration=final_video_visual.duration)
                            final_audio = CompositeAudioClip([voice_audio_combined, bgm_audio])
                        else:
                            final_audio = voice_audio_combined
                            
                        video_with_audio = final_video_visual.with_audio(final_audio)
                    else:
                        video_with_audio = video_muted
                    
                    if logo_file:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_logo:
                            tmp_logo.write(logo_file.read())
                            logo_path = tmp_logo.name
                        
                        logo = (ImageClip(logo_path)
                                .with_duration(video_with_audio.duration)
                                .resized(height=video_with_audio.h // 8)
                                .with_position((20, 20))
                                .with_start(0))
                        
                        final_video = CompositeVideoClip([video_with_audio, logo])
                    else:
                        final_video = video_with_audio
                    
                    output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True)
                    
                    st.success("စိတ်လှုပ်ရှားစရာကောင်းတဲ့ ဇာတ်ကြောင်းပြော Video ရပါပြီ!")
                    st.video(output_video_path)
                    with open(output_video_path, "rb") as f:
                        st.download_button("Download Final Video (MP4)", f, "my_movie_ultra.mp4", "video/mp4")
                    
                    video_clip.close()
                    video_muted.close()
                
                genai.delete_file(video_file_ai.name)
                
            except Exception as e:
                st.error(f"Error: {e}")
elif not api_key and video_path:
    st.warning("Please enter your API Key in the sidebar.")
