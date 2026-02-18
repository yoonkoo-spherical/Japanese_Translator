import streamlit as st
import os
import time
import tempfile
from google import genai
from dotenv import load_dotenv

# 1. 기본 설정 및 환경 변수 로드
load_dotenv()

st.set_page_config(
    page_title="Gemini PDF Researcher",
    page_icon="📚",
    layout="wide"
)

# 2. 사이드바: API 키 및 설정
with st.sidebar:
    st.header("설정")
    env_key = os.getenv("GEMINI_API_KEY")
    api_key = st.text_input("Gemini API Key", value=env_key if env_key else "", type="password")
    
    st.divider()
    st.write("사용 모델: `gemini-flash-latest`")
    st.info("PDF를 드래그 앤 드롭하면 분석합니다.")

# 3. [핵심] 클라이언트 객체 캐싱 함수
# 이 함수는 입력값(api_key)이 같으면 메모리에 저장된 client 객체를 재사용합니다.
# 이를 통해 Streamlit이 재실행될 때 연결이 끊기는 문제를 방지합니다.
@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)

# 4. 메인 로직
st.title("📚 PDF 논문 통합 분석 & 채팅")

# 세션 상태 초기화
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "processed_files" not in st.session_state:
    st.session_state.processed_files = []

# API 클라이언트 초기화 (캐싱된 함수 사용)
if api_key:
    try:
        client = get_gemini_client(api_key)
    except Exception as e:
        st.error(f"API 연결 오류: {e}")
        st.stop()
else:
    st.warning("왼쪽 사이드바에 API 키를 입력해주세요.")
    st.stop()

# 5. 파일 업로드 영역
uploaded_files = st.file_uploader(
    "PDF 파일을 이곳에 드래그 하세요", 
    type=["pdf"], 
    accept_multiple_files=True
)

# 6. 파일 처리 및 초기 분석
if uploaded_files and st.button("파일 분석 시작"):
    # 이미 분석한 파일이면 재분석 방지 (선택 사항)
    current_files = [f.name for f in uploaded_files]
    if st.session_state.processed_files == current_files:
        st.warning("이미 분석된 파일들입니다. 아래 채팅을 이용하세요.")
    else:
        with st.spinner("파일을 Google 서버에 업로드하고 분석 중입니다..."):
            try:
                upload_refs = []
                progress_bar = st.progress(0)
                
                for i, uploaded_file in enumerate(uploaded_files):
                    # 임시 파일 저장
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    # [수정됨] 파일 업로드 (이름표 부착)
                    # display_name을 설정해야 나중에 cleanup 할 때 파일 식별이 쉽습니다.
                    upload_obj = client.files.upload(
                        file=tmp_path,
                        config={'display_name': uploaded_file.name}
                    )
                    
                    # 대기
                    while upload_obj.state.name == "PROCESSING":
                        time.sleep(1)
                        upload_obj = client.files.get(name=upload_obj.name)
                    
                    upload_refs.append(upload_obj)
                    os.remove(tmp_path)
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                # [수정됨] 채팅 세션 생성 (모델명 변경)
                chat = client.chats.create(
                    model="gemini-flash-latest",
                    config={
                        "system_instruction": "당신은 반도체 물리학 전문가입니다. 수식은 LaTeX 문법($...$)을 사용하여 명확하게 표현하세요.",
                    }
                )
                
                # 배치 프롬프트 전송
                initial_prompt = upload_refs + [
                    "1. Analyze all uploaded PDF files.",
                    "2. Provide a detailed summary for EACH file (3 paragraphs: Research Objective, Methodology, Conclusion).",
                    "3. Use LaTeX for math equations.",
                    "4. Output format: ## [Filename]\n(Summary...)"
                ]
                
                response = chat.send_message(initial_prompt)
                
                # 세션 저장
                st.session_state.chat_session = chat
                st.session_state.processed_files = current_files
                
                # 첫 응답 기록
                st.session_state.chat_history = [{"role": "assistant", "text": response.text}]
                
                st.success("분석 완료! 채팅을 시작하세요.")
                st.rerun()
                
            except Exception as e:
                st.error(f"오류 발생: {e}")

# 7. 채팅 인터페이스
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["text"])

if prompt := st.chat_input("질문하세요..."):
    if not st.session_state.chat_session:
        st.error("먼저 파일을 업로드하고 분석을 시작하세요.")
    else:
        st.session_state.chat_history.append({"role": "user", "text": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                try:
                    # 캐싱된 client 덕분에 연결이 유지됨
                    response = st.session_state.chat_session.send_message(prompt)
                    st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "text": response.text})
                except Exception as e:
                    st.error(f"응답 실패: {e}")
                    # 세션 만료 시 복구 제안
                    if "client has been closed" in str(e):
                        st.warning("세션이 만료되었습니다. '파일 분석 시작'을 다시 눌러주세요.")

# 8. 저장 버튼
if st.sidebar.button("대화 내용 저장 (.md)"):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"Gemini_Chat_{timestamp}.md"
    full_text = ""
    for msg in st.session_state.chat_history:
        role = "User" if msg["role"] == "user" else "Gemini"
        full_text += f"\n\n### {role}:\n{msg['text']}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(full_text)
    st.sidebar.success(f"저장 완료: {filename}")
