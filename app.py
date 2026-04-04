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
from pytubefix import YouTube

# Page configuration
st.set_page_config(page_title="AI Burmese Movie Narrator Pro", layout="wide")

st.title("🎬 AI Burmese Movie Narrator Pro")
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

if video_path and api_key:
    if st.button("Generate Branded Narrated Video"):
        with st.spinner("AI က Video ကိုကြည့်ပြီး ဇာတ်ကြောင်းပြောခြင်းနှင့် အကြံပြုချက်များ ထုတ်ပေးနေပါတယ်..."):
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
                
                PART 1: STORYTELLING
                Tell the story of what is happening in an EXCITING, DRAMATIC, and ENGAGING way in BURMESE language.
                - Use natural, spoken Burmese.
                - NO introductions, NO greetings, NO commentary.
                - Format: [start_time - end_time] Story text
                
                PART 2: CATCHY TITLES
                Suggest ONLY 3 catchy, clickbait-style titles in Burmese that would attract viewers on platforms like TikTok or Facebook. These titles should be relevant to the video content.
                - Format: TITLE: [Catchy Burmese Title]
                
                PART 3: TRENDING HASHTAGS
                Suggest ONLY 3 trending hashtags relevant to the video content, suitable for platforms like TikTok. These can be a mix of Burmese and English.
                - Format: HASHTAG: [Trending Hashtag]
                
                PART 4: MOVIE RECOMMENDATIONS
                Suggest ONLY the titles of 3 similar movies that viewers might like.
                - Format: MOVIE_NAME: [Movie Title Only]
                """
                
                response = model.generate_content([video_file_ai, prompt])
                
                if not response.candidates:
                    st.error("AI က ဒီ Video ကို ပိတ်ပင်ထားပါတယ် (Blocked)။")
                else:
                    full_text = response.text
                    
                    # Parse the response into sections
                    narrator_script = ""
                    catchy_titles = []
                    trending_hashtags = []
                    movie_titles = []
                    
                    # Split by section markers
                    lines = full_text.split('\n')
                    current_section = "STORYTELLING"
                    
                    for line in lines:
                        if "PART 2:" in line or "CATCHY TITLES" in line:
                            current_section = "TITLES"
                        elif "PART 3:" in line or "TRENDING HASHTAGS" in line:
                            current_section = "HASHTAGS"
                        elif "PART 4:" in line or "MOVIE RECOMMENDATIONS" in line:
                            current_section = "MOVIES"
                        elif line.strip():
                            if current_section == "STORYTELLING" and not line.startswith("TITLE:") and not line.startswith("HASHTAG:") and not line.startswith("MOVIE_NAME:"):
                                narrator_script += line + "\n"
                            elif current_section == "TITLES" and line.startswith("TITLE:"):
                                title = line.replace("TITLE:", "").strip()
                                if title:
                                    catchy_titles.append(title)
                            elif current_section == "HASHTAGS" and line.startswith("HASHTAG:"):
                                hashtag = line.replace("HASHTAG:", "").strip()
                                if hashtag:
                                    trending_hashtags.append(hashtag)
                            elif current_section == "MOVIES" and line.startswith("MOVIE_NAME:"):
                                movie = line.replace("MOVIE_NAME:", "").strip()
                                if movie:
                                    movie_titles.append(movie)
                    
                    # Display sections
                    st.subheader("📖 Generated Script:")
                    st.write(narrator_script.strip())
                    
                    # Display Catchy Titles
                    if catchy_titles:
                        st.subheader("🎯 Catchy Titles for Social Media:")
                        titles_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(catchy_titles[:3])])
                        st.code(titles_text, language="text")
                    
                    # Display Trending Hashtags
                    if trending_hashtags:
                        st.subheader("📱 Trending Hashtags:")
                        hashtags_text = "\n".join([f"{i+1}. {tag}" for i, tag in enumerate(trending_hashtags[:3])])
                        st.code(hashtags_text, language="text")
                    
                    # Display Movie Recommendations
                    if movie_titles:
                        st.subheader("🎬 Recommended Movies:")
                        movies_text = "\n".join([f"{i+1}. {movie}" for i, movie in enumerate(movie_titles[:3])])
                        st.code(movies_text, language="text")
                    
                    # Process Video
                    video_clip = VideoFileClip(video_path)
                    video_duration = video_clip.duration
                    video_muted = video_clip.without_audio()
                    
                    # Extract only the narrator script part
                    script_lines = narrator_script.strip().split('\n')
                    audio_segments = []
                    video_segments = []
                    current_time = 0
                    
                    for line in script_lines:
                        match = re.search(r'\[(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\]\s*(.*)', line)
                        if match:
                            start_str, end_str, text = match.groups()
                            start_sec = int(start_str.split(':')[0]) * 60 + int(start_str.split(':')[1])
                            end_sec = int(end_str.split(':')[0]) * 60 + int(end_str.split(':')[1])
                            
                            # Cap end_sec to video duration to prevent error
                            end_sec = min(end_sec, video_duration)
                            
                            # Ensure start_sec is also within bounds
                            if start_sec >= video_duration:
                                continue
                            
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
                        final_audio = CompositeAudioClip(audio_segments)
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
                    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", temp_audiofile="temp-audio.m4a", remove_temp=True, verbose=False, logger=None)
                    
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
