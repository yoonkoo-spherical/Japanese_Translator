import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
import time
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
from gtts import gTTS  # 🗣️ TTS(음성 합성) 라이브러리 추가

# 1. 페이지 설정
st.set_page_config(page_title="완전체 AI 통역사", layout="centered")

# 2. API 키 보안 로드
try:
    if "GEMINI_API_KEY" in st.secrets:
        GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=GENAI_API_KEY)
    else:
        st.error("API 키 설정을 확인하세요.")
        st.stop()
except Exception:
    st.error("Secrets 파일을 찾을 수 없습니다.")
    st.stop()

# 3. 모델 설정 (속도 최적화: Lite 모델)
@st.cache_resource
def get_model():
    # 최신 경량화 모델 (없으면 1.5-flash 사용)
    return genai.GenerativeModel('gemini-flash-lite-latest')

model = get_model()

# --- 🛠️ 헬퍼 함수들 ---

def convert_audio_to_wav(audio_bytes):
    """모바일 음성(WebM) -> WAV 변환"""
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except:
        return io.BytesIO(audio_bytes)

def text_to_speech(text, lang='ja'):
    """텍스트를 MP3 음성으로 변환"""
    try:
        # gTTS로 음성 생성
        tts = gTTS(text=text, lang=lang, slow=False)
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return mp3_fp
    except Exception as e:
        st.error(f"음성 생성 실패: {e}")
        return None

def parse_gemini_response(text):
    """
    Gemini가 준 응답을 분석해서 [일본어 / 발음 / 한국어 뜻]으로 분리
    """
    parts = text.split('|')
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    else:
        # 분리 실패 시 원본 그대로 반환
        return text, "", ""

# --- 🎨 UI 시작 ---

st.title("🇯🇵 완전체 AI 통역사")
st.caption("번역 + 발음(로마자) + 음성 재생(TTS)")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 사진", "🎤 음성"])

# ==========================================
# [기능 1] 텍스트 번역 (TTS + 발음 표기)
# ==========================================
with tab1:
    st.markdown("##### 🇰🇷 한국어 → 🇯🇵 일본어")
    text_input = st.text_area("번역할 내용을 입력하세요", height=100)
    
    if st.button("번역하기", key="btn_text"):
        if text_input:
            with st.spinner("번역 및 발음 생성 중..."):
                try:
                    # 프롬프트: 3가지 정보(일본어|발음|뜻)를 '|' 기호로 구분해서 달라고 요청
                    prompt = f"""
                    Translate Korean to Japanese naturally.
                    Output strictly in this format using '|' as separator:
                    
                    Japanese Text (Kanji/Kana) | Pronunciation (Romaji) | Korean Meaning
                    
                    Example: こんにちは | Konnichiwa | 안녕하세요
                    
                    Input: {text_input}
                    """
                    response = model.generate_content(prompt)
                    
                    # 응답 분리
                    jp_text, romaji, kr_mean = parse_gemini_response(response.text)
                    
                    # 1. 결과 화면 표시
                    st.success(f"🇯🇵 **{jp_text}**")  # 크게 일본어
                    st.info(f"🗣️ 읽는 법: **{romaji}**") # 로마자 발음
                    st.caption(f"뜻: {kr_mean}") # 한국어 뜻
                    
                    # 2. 음성 재생 버튼 (TTS)
                    audio_file = text_to_speech(jp_text, 'ja')
                    if audio_file:
                        st.audio(audio_file, format='audio/mp3')

                except Exception as e:
                    st.error(f"오류: {e}")

# ==========================================
# [기능 2] 사진 번역 (발음 포함)
# ==========================================
with tab2:
    st.markdown("##### 📸 메뉴판/안내판 해석")
    uploaded_file = st.file_uploader("사진 선택", type=['jpg', 'png', 'webp'])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="선택한 사진", use_column_width=True)
        
        if st.button("🔍 해석하기"):
            with st.spinner("분석 중..."):
                try:
                    # 이미지 프롬프트 강화
                    prompt = """
                    Find Japanese text in this image.
                    Translate it to Korean.
                    
                    Output format:
                    1. [Summary of the content in Korean]
                    2. Important Words:
                       - [Japanese Text] ([Pronunciation]) : [Korean Meaning]
                    """
                    response = model.generate_content([prompt, image])
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"오류: {e}")

# ==========================================
# [기능 3] 음성 통역 (양방향 TTS)
# ==========================================
with tab3:
    col1, col2 = st.columns(2)
    
    # 한국어 입력
    with col1:
        st.info("🇰🇷 나 (한국어)")
        audio_kr = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️ 멈춤", key='kr')
    
    # 일본어 입력
    with col2:
        st.warning("🇯🇵 상대 (일본어)")
        audio_jp = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️ 멈춤", key='jp')

    # [로직 1] 내가 한국어로 말했을 때 -> 일본어로 번역 + 읽어주기
    if audio_kr:
        with st.spinner("듣고 통역 중..."):
            try:
                # 1. STT (내 말 인식)
                wav_buffer = convert_audio_to_wav(audio_kr['bytes'])
                r = sr.Recognizer()
                with sr.AudioFile(wav_buffer) as source:
                    audio_data = r.record(source)
                    stt_text = r.recognize_google(audio_data, language='ko-KR')
                    st.write(f"🗣️ 나: {stt_text}")
                    
                    # 2. Gemini 번역 (일본어|발음|뜻 포맷)
                    prompt = f"Translate Korean '{stt_text}' to Japanese. Format: Japanese|Romaji|Meaning"
                    response = model.generate_content(prompt)
                    jp_text, romaji, _ = parse_gemini_response(response.text)
                    
                    # 3. 결과 표시
                    st.success(f"🇯🇵 번역: {jp_text}")
                    st.info(f"🗣️ 발음: {romaji}")
                    
                    # 4. 일본어 음성 자동 생성 및 재생 바 표시
                    tts_audio = text_to_speech(jp_text, 'ja')
                    if tts_audio:
                        st.audio(tts_audio, format='audio/mp3', start_time=0)
            except Exception as e:
                st.error("다시 말씀해주세요.")

    # [로직 2] 상대가 일본어로 말했을 때 -> 한국어로 번역 + 읽어주기
    if audio_jp:
        with st.spinner("듣고 통역 중..."):
            try:
                # 1. STT (상대 말 인식)
                wav_buffer = convert_audio_to_wav(audio_jp['bytes'])
                r = sr.Recognizer()
                with sr.AudioFile(wav_buffer) as source:
                    audio_data = r.record(source)
                    stt_text = r.recognize_google(audio_data, language='ja-JP')
                    st.write(f"🗣️ 상대: {stt_text}")
                    
                    # 2. Gemini 번역 (한국어)
                    response = model.generate_content(f"Translate Japanese '{stt_text}' to Korean.")
                    kr_text = response.text
                    
                    # 3. 결과 표시
                    st.success(f"🇰🇷 번역: {kr_text}")
                    
                    # 4. 한국어 음성 생성 (상대 말을 내가 들어야 하니까)
                    tts_audio = text_to_speech(kr_text, 'ko')
                    if tts_audio:
                        st.audio(tts_audio, format='audio/mp3', start_time=0)
            except Exception as e:
                st.error("다시 말씀해주세요.")
