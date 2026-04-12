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

def get_best_model():
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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
        tfile.write(video_file.read())
        video_path = tfile.name

    st.video(video_path)

    if st.button("🚀 Start AI Narration Process"):
        try:
            genai.configure(api_key=api_key)
            
            with st.status("AI is processing...", expanded=True) as status:
                st.write("🔍 Finding best available Gemini model...")
                model, used_model_name = get_best_model()
                if not model:
                    st.error("❌ No supported Gemini models found.")
                    st.stop()

                st.write("📤 Uploading video to AI...")
                gen_file = genai.upload_file(path=video_path, mime_type="video/mp4")
                while gen_file.state.name == "PROCESSING":
                    time.sleep(2)
                    gen_file = genai.get_file(gen_file.name)
                
                st.write("📝 Generating natural Burmese storytelling script...")
                prompt = """
                Analyze this movie clip and write a professional movie recap in BURMESE.
                STYLE: Natural, engaging, human-like (NOT formal). 
                FORMAT:
                [TITLES]
                (Give 3 catchy titles)
                [RECAP]
                (The full story in Burmese)
                """
                response = model.generate_content([gen_file, prompt])
                full_response = response.text

                titles_match = re.search(r"\[TITLES\](.*?)\[RECAP\]", full_response, re.DOTALL)
                recap_match = re.search(r"\[RECAP\](.*)", full_response, re.DOTALL)
                title_list = titles_match.group(1).strip().split('\n') if titles_match else ["Movie Recap"]
                recap_text = recap_match.group(1).strip() if recap_match else full_response

                st.write("🎙️ Creating natural Burmese voiceover...")
                audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                asyncio.run(generate_burmese_audio(recap_text, audio_temp.name))

                st.write("🎬 Finalizing Video, Audio Sync & Subtitles...")
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_temp.name)

                # Mute & Blur
                video_processed = video_clip.fl_image(blur_original_subtitles).without_audio()

                # Sync Video Length
                if audio_clip.duration > video_processed.duration:
                    freeze_duration = audio_clip.duration - video_processed.duration
                    last_frame = video_processed.get_frame(video_processed.duration - 0.1)
                    freeze_clip = ImageClip(last_frame).set_duration(freeze_duration)
                    video_final = concatenate_videoclips([video_processed, freeze_clip])
                else:
                    video_final = video_processed.subclip(0, audio_clip.duration)

                # --- Burmese Subtitles Section ---
                # စာကြောင်းများကို '။' သို့မဟုတ် '.' ဖြင့် ခွဲပါမည်
                sentences = re.split(r'(?<=[။])\s*', recap_text)
                subtitles = []
                duration_per_sentence = video_final.duration / max(len(sentences), 1)
                
                font_path = "Pyidaungsu.ttf" # GitHub ထဲမှာ ဒီဖိုင်ရှိနေဖို့ လိုပါတယ်
                if not os.path.exists(font_path):
                    st.warning("⚠️ Pyidaungsu.ttf font file not found in repository. Subtitles may not show correctly.")
                    font_path = None

                for i, sentence in enumerate(sentences):
                    if sentence.strip():
                        txt_clip = TextClip(
                            sentence.strip(),
                            fontsize=24,
                            color='white',
                            font=font_path,
                            stroke_color='black',
                            stroke_width=1,
                            method='caption',
                            size=(video_final.w * 0.8, None)
                        ).set_start(i * duration_per_sentence).set_duration(duration_per_sentence).set_position(('center', video_final.h - 60))
                        subtitles.append(txt_clip)

                # Combine Video, Audio and Subtitles
                final_result = CompositeVideoClip([video_final] + subtitles).set_audio(audio_clip)
                
                output_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                final_result.write_videofile(output_video_path, codec="libx264", audio_codec="aac", fps=24)
                
                status.update(label="✅ Complete!", state="complete")

            st.success("✨ Your Movie Recap with Subtitles is Ready!")
            st.video(output_video_path)
            
            with open(output_video_path, "rb") as f:
                st.download_button("Download Final Video", f, file_name="burmese_movie_recap.mp4")

            # Cleanup
            video_clip.close()
            audio_clip.close()
            os.remove(audio_temp.name)
            genai.delete_file(gen_file.name)

        except Exception as e:
            st.error(f"An error occurred: {e}")
