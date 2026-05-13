# ... (앞부분 데이터 로드 로직 동일) ...

df_raw = load_filtered_data()

# 검색 설정 (단독 납품 토글)
st.markdown("---")
col_setting, col_blank = st.columns([1, 2])
with col_setting:
    st.markdown("### ⚙️ 검색 설정")
    is_exclusive = st.toggle("🌟 단독 납품(전용) 제품만 보기")

if is_exclusive:
    df = df_raw[~df_raw['납품처'].astype(str).str.contains(',', na=False)]
    st.info("💡 단일 채널 전용 제품만 표시 중입니다.")
else:
    df = df_raw.copy()
st.markdown("---")


# ==========================================
# ✨ 핵심 추가 기능: 동적 컬럼 선택 UI ✨
# ==========================================
st.markdown("### 📊 데이터 표시 설정")

all_cols = ['납품처', '제품코드', '상품명', '환산(재고 수)', '로트번호', '유효일자', '잔여일수', '박스입수', '상품바코드', '특이사항']
# 기본으로 화면에 띄워둘 '핵심 열' 지정
default_cols = ['납품처', '제품코드', '상품명', '환산(재고 수)']

# 사용자가 보고 싶은 열을 맘대로 넣고 뺄 수 있는 멀티셀렉트 박스
selected_cols = st.multiselect(
    "👀 표에서 확인할 항목을 선택하세요 (자유롭게 추가/삭제 가능)",
    options=all_cols,
    default=default_cols
)

# 3. 화면 구성 및 출력 로직
tab1, tab2 = st.tabs(["🏢 채널(납품처) 기준", "🔍 제품명/코드 기준"])

# --- 탭 1: 채널별 검색 ---
with tab1:
    col_input, col_down = st.columns([3, 1])
    with col_input:
        all_customers = df['납품처'].dropna().unique().tolist()
        unique_customers = sorted(list(set([c.strip() for sublist in [str(x).split(',') for x in all_customers] for c in sublist])))
        target = st.selectbox("업체를 선택하세요", ["업체 선택"] + unique_customers)
    
    if target != "업체 선택":
        result = df[df['납품처'].str.contains(target, na=False)]
        with col_down:
            st.write("") 
            st.write("")
            # 다운로드할 때는 화면 설정과 상관없이 '전체 컬럼'을 다운받도록 all_cols 사용
            excel_bin = to_excel(result[all_cols])
            st.download_button(label="📥 전체 데이터 엑셀 다운로드", data=excel_bin, file_name=f"{target}_재고.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        st.metric("가용 재고", f"{len(result)} 건")
        
        # 🚨 화면에 그릴 때는 사용자가 선택한 컬럼(selected_cols)만 출력
        st.dataframe(result[selected_cols], use_container_width=True, hide_index=True, height=550)

# --- 탭 2: 제품별 검색 ---
with tab2:
    search_input = st.text_input("제품명 또는 코드를 입력하세요")
    if search_input:
        result_q = df[
            df['상품명'].str.contains(search_input, case=False, na=False) |
            df['제품코드'].str.contains(search_input, case=False, na=False)
        ]
        if not result_q.empty:
            excel_bin_q = to_excel(result_q[all_cols])
            st.download_button(label="📥 전체 데이터 결과 다운로드", data=excel_bin_q, file_name="검색결과.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.metric("검색 결과", f"{len(result_q)} 건")
            
            # 🚨 여기도 마찬가지로 선택한 컬럼만 출력
            st.dataframe(result_q[selected_cols], use_container_width=True, hide_index=True, height=550)
        else:
            st.warning("가용한 제품 정보가 없습니다.")
