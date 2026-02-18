import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
from PIL import Image
import io
import time
import streamlit.components.v1 as components  # 자바스크립트 TTS용
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment

# ==========================================
# 1. 기본 설정 및 초기화
# ==========================================
st.set_page_config(page_title="AI 통역사 Pro", layout="centered")

# API 키 로드 (Secrets 또는 로컬)
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        st.stop()
except Exception:
    st.error("⚠️ Secrets 파일을 찾을 수 없습니다.")
    st.stop()

# 모델 설정 (가장 빠른 Lite 모델 사용)
@st.cache_resource
def get_model():
    # 최신 경량화 모델 (없으면 1.5-flash 자동 대체)
    try:
        model = genai.GenerativeModel('gemini-flash-lite-latest')
        return model
    except:
        return genai.GenerativeModel('gemini-flash-latest')

model = get_model()

# ==========================================
# 2. 핵심 유틸리티 함수들
# ==========================================

def ask_gemini(content):
    """
    Gemini에게 요청을 보내고, 429(Too Many Requests) 에러 발생 시
    자동으로 재시도하는 안전장치 함수입니다.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return model.generate_content(content)
        except Exception as e:
            if "429" in str(e): # 사용량 초과 시
                time.sleep(2)   # 2초 대기 후 재시도
                continue
            else:
                st.error(f"오류 발생: {e}")
                return None
    st.error("이용자가 많아 지연되고 있습니다. 잠시 후 다시 시도해주세요.")
    return None

def autoplay_audio(text, lang='ja'):
    """
    서버를 거치지 않고 사용자 브라우저(폰)에서 즉시 읽게 만드는 JS 코드.
    속도가 0초에 가깝습니다.
    """
    # 언어 코드 설정 (일본어: ja-JP, 한국어: ko-KR)
    lang_code = 'ja-JP' if lang == 'ja' else 'ko-KR'
    
    js_code = f"""
    <script>
        var msg = new SpeechSynthesisUtterance("{text}");
        msg.lang = "{lang_code}";
        msg.rate = 1.0; 
        window.speechSynthesis.speak(msg);
    </script>
    """
    # 화면에 보이지 않게 실행
    components.html(js_code, height=0)

def convert_audio_to_wav(audio_bytes):
    """모바일(WebM) 오디오를 PC용(WAV)으로 변환"""
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        buffer.seek(0)
        return buffer
    except:
        return io.BytesIO(audio_bytes)

def parse_response(text):
    """응답 텍스트에서 '|' 기호를 기준으로 분리"""
    parts = text.split('|')
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    return text, "", ""

# ==========================================
# 3. 메인 UI 구성
# ==========================================

st.title("🇯🇵 AI 실시간 통역기")
st.caption("🚀 초고속 Lite 모델 | 🗣️ 즉시 듣기 | 🛡️ 에러 방지")

tab1, tab2, tab3 = st.tabs(["📝 텍스트", "📷 사진", "🎤 대화"])

# --- [Tab 1] 텍스트 번역 ---
with tab1:
    st.markdown("##### 🇰🇷 한국어 ↔ 🇯🇵 일본어")
    text_input = st.text_area("내용 입력", height=100, placeholder="안녕하세요, 얼마인가요?")
    
    if st.button("번역 및 듣기", key="btn_text"):
        if text_input:
            with st.spinner(".."):
                # 프롬프트: 3단 분리 요청
                prompt = f"""
                Translate Korean to Japanese naturally.
                Output format: Japanese Text|Romaji Pronunciation|Korean Meaning
                Input: {text_input}
                """
                response = ask_gemini(prompt)
                
                if response:
                    jp, rom, mean = parse_response(response.text)
                    st.success(f"🇯🇵 {jp}")
                    st.info(f"🗣️ {rom}")
                    st.caption(f"뜻: {mean}")
                    
                    # 즉시 재생
                    autoplay_audio(jp, 'ja')

# --- [Tab 2] 사진 번역 ---
with tab2:
    st.markdown("##### 📸 메뉴판/안내문 해석")
    uploaded_file = st.file_uploader("이미지 선택", type=['jpg', 'png', 'webp'])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="선택된 이미지", use_column_width=True)
        
        if st.button("🔍 해석하기"):
            with st.spinner("분석 중.."):
                prompt = """
                Find Japanese text and translate to Korean.
                Output format:
                1. [Summary]
                2. [Original] ([Pronunciation]) -> [Meaning]
                """
                # 이미지 리사이징 없이 전송 (Lite 모델은 처리 빠름)
                response = ask_gemini([prompt, image])
                if response:
                    st.markdown(response.text)

# --- [Tab 3] 음성 대화 (양방향) ---
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

    # [로직 1] 내가 말할 때
    if audio_kr:
        with st.spinner("통역 중.."):
            wav = convert_audio_to_wav(audio_kr['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as source:
                    audio_data = r.record(source)
                    stt = r.recognize_google(audio_data, language='ko-KR')
                    st.write(f"🗣️ 나: {stt}")
                    
                    # 번역 요청
                    prompt = f"Translate to Japanese. Format: Japanese|Romaji|Meaning. Input: {stt}"
                    res = ask_gemini(prompt)
                    
                    if res:
                        jp, rom, _ = parse_response(res.text)
                        st.success(f"🇯🇵 {jp}")
                        st.caption(f"발음: {rom}")
                        # 일본어로 즉시 말하기
                        autoplay_audio(jp, 'ja')
            except sr.UnknownValueError:
                st.error("목소리를 인식하지 못했습니다.")
            except Exception as e:
                st.error(f"오류: {e}")

    # [로직 2] 상대가 말할 때
    if audio_jp:
        with st.spinner("통역 중.."):
            wav = convert_audio_to_wav(audio_jp['bytes'])
            r = sr.Recognizer()
            try:
                with sr.AudioFile(wav) as source:
                    audio_data = r.record(source)
                    stt = r.recognize_google(audio_data, language='ja-JP')
                    st.write(f"🗣️ 상대: {stt}")
                    
                    # 번역 요청
                    res = ask_gemini(f"Translate Japanese to Korean: {stt}")
                    
                    if res:
                        st.success(f"🇰🇷 {res.text}")
                        # 한국어로 즉시 말하기
                        autoplay_audio(res.text, 'ko')
            except sr.UnknownValueError:
                st.error("목소리를 인식하지 못했습니다.")
            except Exception as e:
                st.error(f"오류: {e}")
