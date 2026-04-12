import streamlit as st
import google.generativeai as genai
import os
import asyncio
import edge_tts
import time
import re
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip
from moviepy.config import change_settings

# --- MoviePy FFMPEG Configuration (Streamlit Cloud Fix) ---
try:
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    change_settings({"FFMPEG_BINARY": ffmpeg_path})
except Exception:
    for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if os.path.exists(path):
            change_settings({"FFMPEG_BINARY": path})
            break

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

# Initialize file paths to None to avoid NameError in finally block
video_path = None
audio_path = None
output_video_path = None
gen_file_name = None

if video_file and api_key:
    video_path = "input_video.mp4"
    with open(video_path, "wb") as f:
        f.write(video_file.read())

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
                gen_file_name = gen_file.name
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
                    full_response = response.text
                except Exception as e:
                    if "429" in str(e):
                        st.error("⚠️ Gemini API Quota ပြည့်သွားပါပြီ။ ခဏစောင့်ပြီးမှ ပြန်ကြိုးစားပေးပါ။ (သို့မဟုတ်) API Key အသစ်တစ်ခု အသုံးပြုပါ။")
                        st.stop()
                    else:
                        raise e

                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_path = "narration_audio.mp3"
                asyncio.run(generate_burmese_audio(recap_text, audio_path))

                st.write("🎬 Finalizing Video & Audio Sync (Simple Freeze)...")
                
                # MoviePy ကို အသုံးပြုပြီး ရိုးရှင်းစွာ ပေါင်းစပ်ပါသည်
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_path)
                
                # အသံက ဗီဒီယိုထက် ရှည်နေလျှင်
                if audio_clip.duration > video_clip.duration:
                    # ၁။ ဗီဒီယိုရဲ့ နောက်ဆုံး frame ကို ပုံအဖြစ် ယူပါသည်
                    last_frame = video_clip.get_frame(video_clip.duration - 0.01)
                    
                    # ၂။ အဲဒီပုံကို လိုအပ်သလောက် duration (freeze) ပေးလိုက်ပါသည်
                    freeze_duration = audio_clip.duration - video_clip.duration
                    freeze_clip = ImageClip(last_frame).set_duration(freeze_duration).set_start(video_clip.duration)
                    
                    # ၃။ မူရင်းဗီဒီယိုနဲ့ freeze clip ကို ပေါင်းပါသည်
                    final_video = CompositeVideoClip([video_clip, freeze_clip])
                else:
                    # ဗီဒီယိုက ပိုရှည်နေလျှင် အသံပြီးဆုံးချိန်မှာ ဖြတ်ပါသည်
                    final_video = video_clip.subclip(0, audio_clip.duration)
                
                # အသံထည့်ပါသည်
                final_video = final_video.set_audio(audio_clip)
                
                output_video_path = "final_output.mp4"
                final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=24, logger=None)
                
                # Close clips to release files
                video_clip.close()
                audio_clip.close()
                
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

            # Cleanup Gemini file
            if gen_file_name:
                genai.delete_file(gen_file_name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            # Safe cleanup of local files
            for f in [video_path, audio_path, output_video_path]:
                if f and os.path.exists(f):
                    try: os.remove(f)
                    except: pass
