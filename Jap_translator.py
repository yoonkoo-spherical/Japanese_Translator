import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment  # 오디오 변환을 위해 추가된 핵심 라이브러리

# 1. 페이지 설정
st.set_page_config(page_title="모바일 최적화 번역기", layout="centered")

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
    # 최신 경량화 모델 사용 (없으면 flash 사용)
    return genai.GenerativeModel('gemini-flash-lite-latest')

model = get_model()

# --- 오디오 변환 함수 (핵심 기능) ---
def convert_audio_to_wav(audio_bytes):
    """
    모바일(WebM/MP4)에서 온 오디오를 PC가 좋아하는 WAV로 강제 변환합니다.
    이 과정이 없으면 모바일 음성 인식이 99% 실패합니다.
    """
    try:
        # 1. 바이트 데이터를 오디오 세그먼트로 로드 (WebM일 가능성이 높음)
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        # 2. WAV 포맷으로 변환하여 메모리에 저장
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except Exception as e:
        # 변환 실패 시 원본 반환 (혹시 모르니)
        return io.BytesIO(audio_bytes)

st.title("⚡ 모바일 AI 통역기")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 사진", "🎤 음성"])

# --- [기능 1] 텍스트 번역 ---
with tab1:
    text_input = st.text_area("입력 (자동감지)", height=100)
    if st.button("번역", key="btn_text"):
        if text_input:
            with st.spinner(".."):
                try:
                    prompt = f"Translate naturally. KR <-> JP. Text: {text_input}"
                    response = model.generate_content(prompt)
                    st.success(response.text)
                except Exception as e:
                    st.error(f"Error: {e}")

# --- [기능 2] 사진 번역 ---
with tab2:
    uploaded_file = st.file_uploader("사진 선택", type=['jpg', 'png', 'webp'])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="이미지", use_column_width=True)
        if st.button("해석"):
            with st.spinner("분석 중.."):
                try:
                    res = model.generate_content(["Find Japanese text and translate to Korean.", image])
                    st.markdown(res.text)
                except Exception as e:
                    st.error(f"Error: {e}")

# --- [기능 3] 음성 통역 (모바일 패치 적용됨) ---
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.info("🇰🇷 나")
        audio_kr = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️", key='kr')
    with col2:
        st.warning("🇯🇵 상대")
        audio_jp = mic_recorder(start_prompt="🔴 말하기", stop_prompt="⏹️", key='jp')

    # 한국어 처리
    if audio_kr:
        with st.spinner("변환 및 인식 중..."):
            try:
                # 1. 오디오 포맷 변환 (WebM -> WAV)
                wav_buffer = convert_audio_to_wav(audio_kr['bytes'])
                
                # 2. 음성 인식
                r = sr.Recognizer()
                with sr.AudioFile(wav_buffer) as source:
                    audio_data = r.record(source)
                    stt_text = r.recognize_google(audio_data, language='ko-KR')
                    st.write(f"🗣️ 인식: {stt_text}")
                    
                    # 3. Gemini 번역
                    res = model.generate_content(f"Translate Korean to Japanese: {stt_text}")
                    st.success(f"🇯🇵 {res.text}")
            except Exception as e:
                st.error(f"인식 실패: {e}")

    # 일본어 처리
    if audio_jp:
        with st.spinner("변환 및 인식 중..."):
            try:
                # 1. 오디오 포맷 변환 (WebM -> WAV)
                wav_buffer = convert_audio_to_wav(audio_jp['bytes'])
                
                # 2. 음성 인식
                r = sr.Recognizer()
                with sr.AudioFile(wav_buffer) as source:
                    audio_data = r.record(source)
                    stt_text = r.recognize_google(audio_data, language='ja-JP')
                    st.write(f"🗣️ 인식: {stt_text}")
                    
                    # 3. Gemini 번역
                    res = model.generate_content(f"Translate Japanese to Korean: {stt_text}")
                    st.success(f"🇰🇷 {res.text}")
            except Exception as e:
                st.error(f"인식 실패: {e}")
