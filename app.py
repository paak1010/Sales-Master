import streamlit as st
import pandas as pd
from io import BytesIO
import glob
import os
import base64

# ==========================================
# 1. 페이지 테마 및 스타일 설정 
# ==========================================
st.set_page_config(page_title="Rohto Mentholatum Inventory", layout="wide", initial_sidebar_state="expanded")

def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return ""

logo_base64 = get_base64_of_bin_file('logo.png')

st.markdown(f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * {{ font-family: 'Pretendard', sans-serif !important; }}
    .stApp {{ background-color: #ffffff; }}
    
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    div[data-testid="stDecoration"] {{display: none;}}

    .block-container {{ padding-top: 3.5rem !important; padding-bottom: 3rem !important; }}
    
    /* 우측 상단 로고 */
    .top-right-logo {{ position: fixed; top: 20px; right: 30px; width: 140px; z-index: 999999; }}

    [data-testid="stSidebar"] {{ background-color: #ffffff; border-right: 1px solid #e0e0e0; }}
    
    .stButton > button {{
        width: 100%; background-color: #ffffff; color: #006838;
        border: 1px solid #006838; border-radius: 4px; font-weight: 600; transition: 0.3s;
    }}
    .stButton > button:hover {{ background-color: #006838; color: #ffffff; }}

    div[data-testid="metric-container"] {{ background-color: transparent !important; border: none !important; box-shadow: none !important; padding: 0px !important; }}
    div[data-testid="stMetricLabel"] {{ font-size: 13px !important; color: #666666 !important; font-weight: 500 !important; margin-bottom: -5px; }}
    div[data-testid="stMetricValue"] {{ font-size: 32px !important; font-weight: 400 !important; color: #1a1a1a !important; }}

    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border: 1px solid #e0e0e0; border-radius: 8px; }}
    </style>
""", unsafe_allow_html=True)

if logo_base64:
    st.markdown(f'<img src="data:image/png;base64,{logo_base64}" class="top-right-logo">', unsafe_allow_html=True)

# --- 엑셀 변환 헬퍼 함수 ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventory_Report')
    return output.getvalue()

def get_latest_stock_file():
    stock_files = glob.glob("Sales_Stock_*.xlsx")
    return sorted(stock_files, reverse=True)[0] if stock_files else None

# 🚀 [피드백 1] PAL / BOX 단위 환산 함수 (임시 매핑)
def convert_to_pal_box(qty, me_code):
    # TODO: 재현님! 여기에 실제 제품별 입수량 마스터를 연결하시면 됩니다.
    # 예시: '제품코드': (BOX당 EA입수, PAL당 BOX입수)
    MASTER_PACKING = {
        'ME00421200': (20, 40),
        'ME00421300': (20, 40)
    }
    box_ea, pal_box = MASTER_PACKING.get(me_code, (10, 50)) # 등록 안된 코드는 기본 10EA/50BOX 로 계산
    
    pal = int(qty // (box_ea * pal_box))
    rem_ea = qty % (box_ea * pal_box)
    box = int(rem_ea // box_ea)
    ea = rem_ea % box_ea
    
    res = []
    if pal > 0: res.append(f"{pal} PAL")
    if box > 0: res.append(f"{box} BOX")
    if ea > 0: res.append(f"{ea} EA")
    return " / ".join(res) if res else "0 EA"

# 🚀 [피드백 2] 유효일자 Base로 팝업 뷰 변경
@st.dialog("📋 유효일자별 상세 재고 명세", width="large")
def show_lot_details(df_detail, product_name):
    st.markdown(f"<h3 style='font-size: 24px; color: #006838; margin-bottom: 20px;'>📦 {product_name}</h3>", unsafe_allow_html=True)
    
    # 💡 로트 번호 제외하고 '유효일자' 기준으로만 합산! (여러 로트가 섞여도 유효일자가 같으면 하나로 합침)
    merged_detail = df_detail.groupby(['유효일자', '잔여일수', '재고유형'], dropna=False, as_index=False)['수량'].sum()
    merged_detail = merged_detail.sort_values(by='잔여일수').reset_index(drop=True)
    merged_detail.rename(columns={'수량': '합산 수량'}, inplace=True)

    styled_df = merged_detail.style.set_properties(**{'font-size': '15px', 'font-weight': '500'})

    st.dataframe(
        styled_df, use_container_width=True, hide_index=True,
        column_config={
            "잔여일수": st.column_config.ProgressColumn("유통기한 잔여", format="%d일", min_value=0, max_value=1095),
            "합산 수량": st.column_config.NumberColumn("가용 수량", format="%d EA"),
            "유효일자": st.column_config.DateColumn("유효일자"),
            "재고유형": st.column_config.TextColumn("상태")
        }
    )

# ==========================================
# 2. 데이터 로드 및 전처리
# ==========================================
@st.cache_data
def load_and_process_data(stock_file, mapping_mtime):
    mapping_file = "매핑용.xlsx"
    try:
        df_stock = pd.read_excel(stock_file, sheet_name="재고현황", header=1)
        df_stock.columns = df_stock.columns.astype(str).str.strip()
        
        df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2")
        df_channel.columns = df_channel.columns.astype(str).str.strip()
        if '제품코드' not in df_channel.columns:
            df_channel = pd.read_excel(mapping_file, sheet_name="Sheet2", header=1)
            df_channel.columns = df_channel.columns.astype(str).str.strip()
            
        df_stock['상품코드_key'] = df_stock['상품코드'].astype(str).str.strip().str.upper()
        df_channel['제품코드_key'] = df_channel['제품코드'].astype(str).str.strip().str.upper()

        mapping_sub = df_channel[['Customer', '제품코드_key', 'Remarks', 'Sales Team', 'Channel']].dropna(subset=['제품코드_key']).drop_duplicates('제품코드_key')
        df_merged = pd.merge(df_stock, mapping_sub, left_on="상품코드_key", right_on="제품코드_key", how="left")
        
        df_merged.rename(columns={
            'Customer': '납품처', '상품코드': '제품코드', '화주LOT': '로트번호',
            '환산': '수량', 'Remarks': '특이사항', 'Sales Team': '영업팀'
        }, inplace=True)

        df_merged['로트번호'] = df_merged['로트번호'].fillna('').astype(str).str.strip()
        df_merged = df_merged[(df_merged['로트번호'] != '') & (df_merged['로트번호'].str.lower() != 'nan')]
        
        # 🚀 [피드백 4] 삭제하지 않고 재고 유형(가용/불가/Raw) 분류
        df_merged['재고유형'] = '정상가용'
        bad_lots = '불량|폐기|약국반품|회송예정|ZPK'
        raw_lots = '임시적치|임가공|Raw|기본재고|벌크'
        
        df_merged.loc[df_merged['로트번호'].str.contains(bad_lots, case=False, na=False), '재고유형'] = '가용불가'
        df_merged.loc[df_merged['로트번호'].str.contains(raw_lots, case=False, na=False), '재고유형'] = 'Raw재고'

        df_merged['납품처'] = df_merged['납품처'].fillna('미지정').astype(str).str.strip()
        df_merged['영업팀'] = df_merged['영업팀'].fillna('미분류').astype(str).str.strip()
        df_merged['특이사항'] = df_merged['특이사항'].fillna('').astype(str).str.strip()

        # 🚀 [피드백 5] 납품처 텍스트 간소화 (필요한 약어 계속 추가하세요!)
        CUST_MAP = {
            "디에이치 인터네셔널": "DH",
            "쿠팡로켓": "CP",
            "올리브영": "OY",
            "주식회사 무신사": "무신사",
            "Tesco, E-mart": "이마트"
        }
        for k, v in CUST_MAP.items():
            df_merged['납품처'] = df_merged['납품처'].str.replace(k, v)

        if '유효일자' in df_merged.columns:
            df_merged['유효일자'] = pd.to_datetime(df_merged['유효일자'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        return df_merged
    except Exception as e:
        st.error(f"데이터 연동 에러: {e}")
        return None

latest_file = get_latest_stock_file()
if not latest_file:
    st.error("Sales_Stock_*.xlsx 파일이 없습니다.")
    st.stop()

mapping_mtime = os.path.getmtime("매핑용.xlsx") if os.path.exists("매핑용.xlsx") else 0
df_raw = load_and_process_data(latest_file, mapping_mtime)
if df_raw is None: st.stop()

# ==========================================
# 3. 사이드바 UI 및 필터
# ==========================================
with st.sidebar:
    st.markdown("<h3 style='font-size:16px; color:#1a1a1a;'>⚙️ Filter Option</h3>", unsafe_allow_html=True)
    is_exclusive = st.toggle("🌟 전용 납품 품목만 보기")
    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
    
    all_customers = sorted(list(set(part.strip() for c in df_raw['납품처'].dropna() for part in str(c).split(',') if part.strip())))
    selected_customer = st.selectbox("🏢 납품처", ["전체"] + all_customers)
    
    all_teams = sorted(list(set(part.strip() for t in df_raw['영업팀'].dropna() for part in str(t).split(',') if part.strip())))
    selected_team = st.selectbox("👥 영업팀", ["전체"] + all_teams)
    
    search_q = st.text_input("🔍 Search", placeholder="제품명 또는 코드 입력")
    
df_filtered = df_raw.copy()
if is_exclusive: df_filtered = df_filtered[~df_filtered['납품처'].astype(str).str.contains(',', na=False)]
if selected_customer != "전체": df_filtered = df_filtered[df_filtered['납품처'].apply(lambda x: selected_customer in [c.strip() for c in str(x).split(',')])]
if selected_team != "전체": df_filtered = df_filtered[df_filtered['영업팀'].apply(lambda x: selected_team in [t.strip() for t in str(x).split(',')])]
if search_q: df_filtered = df_filtered[df_filtered['상품명'].str.contains(search_q, case=False, na=False) | df_filtered['제품코드'].str.contains(search_q, case=False, na=False)]

# ==========================================
# 4. 메인 대시보드 및 데이터 집계
# ==========================================
st.markdown("<h1 style='font-size: 28px; color: #1a1a1a; margin-bottom: 20px;'>Inventory Mastering Dashboard</h1>", unsafe_allow_html=True)

if not df_filtered.empty:
    # 집계 로직: 상품별로 그룹화하되, 재고유형별 수량도 계산
    df_agg = df_filtered.groupby(['상품바코드', '제품코드']).agg({
        '상품명': 'first', '납품처': 'first', '영업팀': 'first', '특이사항': 'first'
    }).reset_index()

    # 가용 / 가용불가 / Raw 수량 계산
    qty_pivot = df_filtered.pivot_table(index='제품코드', columns='재고유형', values='수량', aggfunc='sum', fill_value=0).reset_index()
    
    # pivot에 없는 컬럼 안전하게 추가
    for col in ['정상가용', '가용불가', 'Raw재고']:
        if col not in qty_pivot.columns: qty_pivot[col] = 0
        
    df_main = pd.merge(df_agg, qty_pivot, on='제품코드', how='left')
    
    # 🚀 [피드백 4] 특이사항에 태깅 추가
    def build_remark(row):
        base_remark = str(row['특이사항']) if str(row['특이사항']) != 'nan' else ""
        tags = []
        if row['가용불가'] > 0: tags.append(f"🛑불가:{row['가용불가']}ea")
        if row['Raw재고'] > 0: tags.append(f"📦Raw:{row['Raw재고']}ea")
        tag_str = " ".join(tags)
        if base_remark and tag_str: return f"{base_remark} / {tag_str}"
        return base_remark + tag_str
        
    df_main['상세_특이사항'] = df_main.apply(build_remark, axis=1)
    
    # 🚀 [피드백 1] PAL/BOX 입수량 텍스트 생성
    df_main['단위(PAL/BOX)'] = df_main.apply(lambda x: convert_to_pal_box(x['정상가용'], x['제품코드']), axis=1)

    # UI 노출용 최종 DataFrame 정리
    df_display = df_main[['납품처', '영업팀', '제품코드', '상품명', '정상가용', '단위(PAL/BOX)', '상세_특이사항', '상품바코드']].copy()
    df_display.rename(columns={'정상가용': '가용 재고(EA)', '상세_특이사항': '특이사항'}, inplace=True)

    # 지표 카드
    m1, m2, m3 = st.columns(3)
    m1.metric("총 취급 품목수", f"{len(df_main)} SKUs")
    m2.metric("총 가용 수량", f"{df_main['가용 재고(EA)'].sum():,} EA")
    with m3:
        st.write(" ")
        st.download_button("📥 Excel Export", data=to_excel(df_display.drop(columns=['상품바코드'])), file_name=f"Stock_Report_{latest_file}.xlsx")

    st.markdown("<hr style='margin:10px 0; border:1px solid #eaeaea;'>", unsafe_allow_html=True)
    
    # 🚀 [피드백 3] 특이사항 쓰기 권한 부여 (st.data_editor 활용)
    st.caption("💡 표의 **'특이사항'** 열을 더블클릭하여 메모를 직접 입력/수정할 수 있습니다. (수정 후 Export 시 그대로 저장됩니다.)")
    
    # Data Editor 설정 (특이사항만 편집 가능)
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "상품바코드": None, # 숨김 처리
            "가용 재고(EA)": st.column_config.NumberColumn(format="%d"),
            "특이사항": st.column_config.TextColumn(
                "특이사항 ✏️", 
                help="더블클릭하여 내용을 수정하세요.",
                max_chars=100
            )
        },
        disabled=["납품처", "영업팀", "제품코드", "상품명", "가용 재고(EA)", "단위(PAL/BOX)"], # 나머지는 읽기 전용
        height=500
    )

    # 상세 보기 버튼들을 표 아래에 배치 (data_editor는 내부에 버튼 삽입 불가)
    st.markdown("<br><b>🔍 품목별 로트/유효일자 상세 조회</b>", unsafe_allow_html=True)
    sel_product = st.selectbox("상세 조회할 품목을 선택하세요:", df_display['상품명'].tolist())
    if st.button("조회하기"):
        sel_row = df_display[df_display['상품명'] == sel_product].iloc[0]
        df_detail = df_filtered[
            (df_filtered['상품바코드'] == sel_row['상품바코드']) & 
            (df_filtered['제품코드'] == sel_row['제품코드'])
        ][['로트번호', '유효일자', '잔여일수', '수량', '재고유형']]
        show_lot_details(df_detail, sel_row['상품명'])

else:
    st.warning("조건에 맞는 데이터가 없습니다.")
