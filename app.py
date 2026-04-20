import streamlit as st
import pandas as pd
import os
import json
import zipfile
import tempfile
import base64
import requests
from datetime import datetime
from io import BytesIO

# 页面配置
st.set_page_config(
    page_title="POD产品批量上架工具",
    page_icon="🛍️",
    layout="wide"
)

# 默认配置
DEFAULT_TEMPLATE = {
    "name": "店小秘-地毯POD",
    "fields": {
        "*产品标题": {"type": "text", "default": "Modern Pattern Area Rug for Living Room Bedroom Decor"},
        "*英文标题": {"type": "text", "default": "Modern Pattern Area Rug for Living Room Bedroom Decor"},
        "产品描述": {"type": "text", "default": ""},
        "产品货号": {"type": "auto", "source": "style_code"},
        "*变种属性名称一": {"type": "text", "default": "尺寸"},
        "*变种属性值一": {"type": "auto", "source": "size"},
        "变种属性名称二": {"type": "text", "default": "颜色"},
        "变种属性值二": {"type": "text", "default": "默认"},
        "预览图": {"type": "auto", "source": "preview_url"},
        "*申报价格\n(店铺币种)": {"type": "auto", "source": "price"},
        "SKU货号": {"type": "auto", "source": "sku"},
        "*长（cm）": {"type": "auto", "source": "length"},
        "*宽（cm）": {"type": "auto", "source": "width"},
        "*高（cm）": {"type": "auto", "source": "height"},
        "*重量（g）": {"type": "auto", "source": "weight"},
        "*轮播图": {"type": "auto", "source": "carousel"},
        "*产品素材图": {"type": "auto", "source": "material_url"},
        "识别码类型": {"type": "text", "default": ""},
        "识别码": {"type": "text", "default": ""},
        "站外产品链接": {"type": "text", "default": ""},
        "外包装形状": {"type": "text", "default": ""},
        "外包装类型": {"type": "text", "default": ""},
        "外包装图片": {"type": "text", "default": ""},
        "建议售价（USD）": {"type": "text", "default": ""},
        "库存": {"type": "number", "default": 999},
        "发货时效（天）": {"type": "number", "default": 2},
        "产地": {"type": "text", "default": "中国"},
    }
}

DEFAULT_RULES = {
    "image_naming": {
        "pattern": "style_number",  # 款号-图片编号 或 未标题-1(1)_编号
        "description": "图片命名格式：款号-图片编号 或 PS导出格式(未标题-1(1)_01)"
    },
    "size_mapping": {
        "01": {"size": "40*60cm", "price": 100, "length": 30, "width": 20, "height": 10, "weight": 800},
        "02": {"size": "40*120cm", "price": 190, "length": 35, "width": 25, "height": 12, "weight": 1500},
        "04": {"size": "80*120cm", "price": 240, "length": 40, "width": 30, "height": 15, "weight": 2500},
    },
    "image_count": 8  # 每个款号最多8张图
}

# 配置文件路径
CONFIG_DIR = "config"
TEMPLATE_FILE = os.path.join(CONFIG_DIR, "templates.json")
RULES_FILE = os.path.join(CONFIG_DIR, "rules.json")

# 加载或创建配置
def load_config(filepath, default):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default

def save_config(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ImgBB上传
def upload_to_imgbb(image_bytes, api_key):
    url = "https://api.imgbb.com/1/upload"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    params = {"key": api_key, "image": image_base64}
    try:
        response = requests.post(url, data=params, timeout=60)
        result = response.json()
        if result.get("success"):
            return result["data"]["url"]
    except Exception as e:
        st.error(f"上传失败: {str(e)}")
    return None

# 解析图片文件名
def parse_filename(filename):
    """解析图片文件名，提取款号和图片编号"""
    name = os.path.splitext(filename)[0]
    
    # 格式1: 款号-编号 (如 a-1, b-2)
    if '-' in name and not name.startswith('未标题'):
        parts = name.rsplit('-', 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0], parts[1].zfill(2)
    
    # 格式2: PS导出格式 (如 未标题-1(1)_01)
    if '_' in name:
        style_code, img_num = name.rsplit('_', 1)
        return style_code, img_num.zfill(2)
    
    # 格式3: 纯数字编号
    if name[-2:].isdigit():
        return name[:-2], name[-2:]
    
    return name, "01"

# 主应用
def main():
    st.title("🛍️ POD产品批量上架工具")
    st.markdown("---")
    
    # 侧边栏 - 配置
    with st.sidebar:
        st.header("⚙️ 配置")
        
        # 图床API Key
        imgbb_key = st.text_input("ImgBB API Key", type="password", value="b07ed816eece274d24550cb68c080e9f")
        
        st.markdown("---")
        
        # 尺寸价格配置
        st.subheader("📏 尺寸价格配置")
        st.caption("图片编号对应的尺寸和价格")
        
        rules = load_config(RULES_FILE, DEFAULT_RULES)
        
        # 显示当前规则
        for img_num, info in rules["size_mapping"].items():
            with st.expander(f"图片编号 {img_num} - {info['size']}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    new_size = st.text_input("尺寸", value=info['size'], key=f"size_{img_num}")
                    new_price = st.number_input("价格", value=info['price'], key=f"price_{img_num}")
                with col2:
                    new_length = st.number_input("长(cm)", value=info['length'], key=f"len_{img_num}")
                    new_width = st.number_input("宽(cm)", value=info['width'], key=f"width_{img_num}")
                    new_height = st.number_input("高(cm)", value=info['height'], key=f"height_{img_num}")
                    new_weight = st.number_input("重量(g)", value=info['weight'], key=f"weight_{img_num}")
                
                if st.button("更新", key=f"update_{img_num}"):
                    rules["size_mapping"][img_num] = {
                        "size": new_size,
                        "price": new_price,
                        "length": new_length,
                        "width": new_width,
                        "height": new_height,
                        "weight": new_weight
                    }
                    save_config(RULES_FILE, rules)
                    st.success("已保存")
        
        # 添加新尺寸
        if st.button("➕ 添加新尺寸"):
            st.session_state.show_add_size = True
        
        if st.session_state.get('show_add_size', False):
            with st.form("add_size_form"):
                new_num = st.text_input("图片编号 (如 03, 05)")
                col1, col2 = st.columns(2)
                with col1:
                    add_size = st.text_input("尺寸")
                    add_price = st.number_input("价格", value=100)
                with col2:
                    add_length = st.number_input("长(cm)", value=30)
                    add_width = st.number_input("宽(cm)", value=20)
                    add_height = st.number_input("高(cm)", value=10)
                    add_weight = st.number_input("重量(g)", value=1000)
                
                if st.form_submit_button("添加"):
                    if new_num and add_size:
                        rules["size_mapping"][new_num.zfill(2)] = {
                            "size": add_size,
                            "price": add_price,
                            "length": add_length,
                            "width": add_width,
                            "height": add_height,
                            "weight": add_weight
                        }
                        save_config(RULES_FILE, rules)
                        st.session_state.show_add_size = False
                        st.success("已添加！")
                        st.rerun()
    
    # 主区域
    tab1, tab2 = st.tabs(["📤 上传处理", "📋 使用说明"])
    
    with tab1:
        st.header("上传图片包")
        
        # 上传方式选择
        upload_type = st.radio("上传方式", ["上传ZIP压缩包", "上传多张图片"], horizontal=True)
        
        uploaded_files = []
        
        if upload_type == "上传ZIP压缩包":
            zip_file = st.file_uploader("选择ZIP文件", type=['zip'])
            if zip_file:
                with zipfile.ZipFile(zip_file, 'r') as z:
                    for name in z.namelist():
                        if name.lower().endswith(('.jpg', '.jpeg', '.png')):
                            uploaded_files.append((name, z.read(name)))
        else:
            files = st.file_uploader("选择图片文件", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
            for f in files:
                uploaded_files.append((f.name, f.getvalue()))
        
        if uploaded_files:
            st.success(f"已加载 {len(uploaded_files)} 张图片")
            
            # 预览图片
            with st.expander("📷 图片预览", expanded=False):
                cols = st.columns(4)
                for idx, (name, data) in enumerate(uploaded_files[:8]):
                    with cols[idx % 4]:
                        st.image(data, caption=name.split('/')[-1], use_container_width=True)
                if len(uploaded_files) > 8:
                    st.caption(f"...还有 {len(uploaded_files) - 8} 张图片")
            
            # 处理按钮
            if st.button("🚀 开始处理", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 解析图片
                status_text.text("📋 解析图片文件名...")
                images = {}
                for name, data in uploaded_files:
                    filename = name.split('/')[-1]
                    style_code, img_num = parse_filename(filename)
                    if style_code not in images:
                        images[style_code] = {}
                    images[style_code][img_num] = (filename, data)
                
                st.info(f"识别到 {len(images)} 个款号")
                
                # 上传图片
                status_text.text("☁️ 上传图片到图床...")
                url_map = {}
                total = sum(len(imgs) for imgs in images.values())
                processed = 0
                
                for style_code, imgs in images.items():
                    for img_num, (filename, data) in imgs.items():
                        processed += 1
                        progress_bar.progress(processed / total)
                        status_text.text(f"☁️ 上传中 {processed}/{total}: {filename}")
                        
                        url = upload_to_imgbb(data, imgbb_key)
                        if url:
                            url_map[(style_code, img_num)] = url
                
                status_text.text(f"✅ 上传完成: {len(url_map)}/{total} 张")
                
                # 生成产品数据
                status_text.text("📊 生成产品数据...")
                all_products = []
                
                for style_code, imgs in images.items():
                    # 收集所有图片URL用于轮播图
                    all_urls = []
                    for num in sorted(imgs.keys()):
                        if (style_code, num) in url_map:
                            all_urls.append(url_map[(style_code, num)])
                    
                    # 为每个尺寸生成产品
                    for img_num, size_info in rules["size_mapping"].items():
                        if img_num not in imgs:
                            continue
                        
                        if (style_code, img_num) not in url_map:
                            continue
                        
                        preview_url = url_map[(style_code, img_num)]
                        carousel = "\n".join(all_urls)
                        
                        product = {
                            "*产品标题": "Modern Pattern Area Rug for Living Room Bedroom Decor",
                            "*英文标题": "Modern Pattern Area Rug for Living Room Bedroom Decor",
                            "产品描述": "",
                            "产品货号": style_code,
                            "*变种属性名称一": "尺寸",
                            "*变种属性值一": size_info["size"].replace("*", "x"),
                            "变种属性名称二": "颜色",
                            "变种属性值二": "默认",
                            "预览图": preview_url,
                            "*申报价格\n(店铺币种)": size_info["price"],
                            "SKU货号": f"{style_code}-{img_num}",
                            "*长（cm）": size_info["length"],
                            "*宽（cm）": size_info["width"],
                            "*高（cm）": size_info["height"],
                            "*重量（g）": size_info["weight"],
                            "*轮播图": carousel,
                            "*产品素材图": all_urls[0] if all_urls else preview_url,
                            "识别码类型": "",
                            "识别码": "",
                            "站外产品链接": "",
                            "外包装形状": "",
                            "外包装类型": "",
                            "外包装图片": "",
                            "建议售价（USD）": "",
                            "库存": 999,
                            "发货时效（天）": 2,
                            "产地": "中国",
                        }
                        all_products.append(product)
                
                # 生成Excel
                df = pd.DataFrame(all_products)
                
                # 提供下载
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                
                progress_bar.progress(1.0)
                status_text.text("✅ 处理完成！")
                
                st.success(f"🎉 成功生成 {len(all_products)} 个产品变种")
                
                st.download_button(
                    label="📥 下载Excel文件",
                    data=excel_buffer,
                    file_name=f"店小秘导入_Temu地毯_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    with tab2:
        st.header("使用说明")
        
        st.markdown("""
        ### 📝 图片命名规则
        
        工具支持以下图片命名格式：
        
        **格式1：款号-图片编号**
        - 示例：`a-1.jpg`, `a-2.jpg`, `b-1.jpg`
        - 编号1-8分别对应不同尺寸
        
        **格式2：PS导出格式**
        - 示例：`未标题-1(1)_01.jpg`, `未标题-1(1)_02.jpg`
        - 下划线后的数字为图片编号
        
        ---
        
        ### 📏 尺寸对应关系（默认配置）
        
        | 图片编号 | 尺寸 | 价格 | 包装尺寸 | 重量 |
        |---------|------|------|---------|------|
        | 01 | 40*60cm | 100元 | 30x20x10cm | 800g |
        | 02 | 40*120cm | 190元 | 35x25x12cm | 1500g |
        | 04 | 80*120cm | 240元 | 40x30x15cm | 2500g |
        
        > 可在左侧配置栏自定义修改
        
        ---
        
        ### 🚀 快速开始
        
        1. 在左侧配置栏确认/修改尺寸价格配置
        2. 上传图片ZIP包或多张图片
        3. 点击"开始处理"
        4. 下载生成的Excel文件
        5. 导入店小秘系统
        
        ---
        
        ### 💡 注意事项
        
        - 每个款号建议有8张图片，其中编号01/02/04对应三个尺寸产品
        - 图片编号06-08仅作为轮播图，不会生成独立产品
        - 首次使用请确认ImgBB API Key是否有效
        """)

if __name__ == "__main__":
    main()
