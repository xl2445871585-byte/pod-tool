import streamlit as st
import pandas as pd
import os
import json
import zipfile
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
DEFAULT_RULES = {
    "size_mapping": {
        "01": {"size": "40*60cm", "price": 150, "length": 60, "width": 40, "height": 3, "weight": 200},
        "02": {"size": "40*120cm", "price": 200, "length": 122, "width": 40, "height": 3, "weight": 300},
        "04": {"size": "80*120cm", "price": 250, "length": 120, "width": 80, "height": 3, "weight": 800},
        "05": {"size": "160*180cm", "price": 400, "length": 160, "width": 38, "height": 38, "weight": 2000},
    },
    "carousel_range": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"],  # 轮播图编号
    "detail_range": ["03", "04", "05", "06", "07", "08", "09", "10"],  # 详情图编号
    "material_image": "01",  # 产品素材图编号
}

# 配置文件路径
CONFIG_DIR = "config"
RULES_FILE = os.path.join(CONFIG_DIR, "rules.json")
TEMPLATES_DIR = os.path.join(CONFIG_DIR, "templates")

# 确保目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

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

# 获取所有模板
def get_templates():
    templates = {}
    if os.path.exists(TEMPLATES_DIR):
        for file in os.listdir(TEMPLATES_DIR):
            if file.endswith('.xlsx'):
                name = file.replace('.xlsx', '')
                templates[name] = os.path.join(TEMPLATES_DIR, file)
    return templates

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
    
    # 格式1: 款号-编号 (如 DDD-341-01, a-1)
    parts = name.rsplit('-', 1)
    if len(parts) == 2:
        style_code = parts[0]
        img_num = parts[1].zfill(2)
        if img_num.isdigit():
            return style_code, img_num
    
    # 格式2: PS导出格式 (如 未标题-1(1)_01)
    if '_' in name:
        style_code, img_num = name.rsplit('_', 1)
        return style_code, img_num.zfill(2)
    
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
        
        # 加载规则
        rules = load_config(RULES_FILE, DEFAULT_RULES)
        
        # 尺寸价格配置
        st.subheader("📏 尺寸价格配置")
        st.caption("图片编号对应的尺寸和价格")
        
        for img_num, info in list(rules["size_mapping"].items()):
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
                        "size": new_size, "price": new_price,
                        "length": new_length, "width": new_width,
                        "height": new_height, "weight": new_weight
                    }
                    save_config(RULES_FILE, rules)
                    st.success("已保存")
        
        # 添加新尺寸
        if st.button("➕ 添加新尺寸"):
            st.session_state.show_add_size = True
        
        if st.session_state.get('show_add_size', False):
            with st.form("add_size_form"):
                new_num = st.text_input("图片编号 (如 03, 06)")
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
                            "size": add_size, "price": add_price,
                            "length": add_length, "width": add_width,
                            "height": add_height, "weight": add_weight
                        }
                        save_config(RULES_FILE, rules)
                        st.session_state.show_add_size = False
                        st.success("已添加！")
                        st.rerun()
        
        st.markdown("---")
        
        # 图片用途配置
        st.subheader("🖼️ 图片用途配置")
        
        carousel_input = st.text_input("轮播图编号", value=",".join(rules.get("carousel_range", ["01","02","03","04","05","06","07","08","09","10"])))
        detail_input = st.text_input("详情图编号", value=",".join(rules.get("detail_range", ["03","04","05","06","07","08","09","10"])))
        material_input = st.text_input("产品素材图编号", value=rules.get("material_image", "01"))
        
        if st.button("保存图片配置"):
            rules["carousel_range"] = [x.strip().zfill(2) for x in carousel_input.split(",")]
            rules["detail_range"] = [x.strip().zfill(2) for x in detail_input.split(",")]
            rules["material_image"] = material_input.zfill(2)
            save_config(RULES_FILE, rules)
            st.success("已保存")
    
    # 主区域 - 标签页
    tab1, tab2, tab3 = st.tabs(["📤 模板处理", "📚 模板管理", "📋 使用说明"])
    
    # ========== 模板处理 ==========
    with tab1:
        st.header("基于模板生成新产品")
        
        # 获取已保存的模板
        templates = get_templates()
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # 选择模板来源
            template_source = st.radio("模板来源", ["已保存的模板", "上传新模板"], horizontal=True)
            
            template_df = None
            template_name = ""
            
            if template_source == "已保存的模板":
                if templates:
                    template_name = st.selectbox("选择模板", list(templates.keys()))
                    if template_name:
                        template_df = pd.read_excel(templates[template_name])
                        st.success(f"已加载模板: {template_name}")
                else:
                    st.warning("暂无已保存的模板，请先上传模板")
            else:
                uploaded_template = st.file_uploader("上传模板Excel", type=['xlsx'])
                if uploaded_template:
                    template_df = pd.read_excel(uploaded_template)
                    template_name = st.text_input("模板名称（可选，用于保存）")
                    st.success("模板已加载")
            
            if template_df is not None:
                with st.expander("查看模板信息", expanded=False):
                    st.write(f"变种数量: {len(template_df)}")
                    if len(template_df) > 0:
                        st.write("尺寸:", template_df['变种属性值一'].tolist())
        
        with col2:
            # 上传图片
            st.subheader("上传图片包")
            upload_type = st.radio("上传方式", ["上传ZIP压缩包", "上传多张图片"], horizontal=True)
            
            uploaded_files = []
            
            if upload_type == "上传ZIP压缩包":
                zip_file = st.file_uploader("选择ZIP文件", type=['zip'], key="zip_uploader")
                if zip_file:
                    with zipfile.ZipFile(zip_file, 'r') as z:
                        for name in z.namelist():
                            if name.lower().endswith(('.jpg', '.jpeg', '.png')):
                                uploaded_files.append((os.path.basename(name), z.read(name)))
            else:
                files = st.file_uploader("选择图片文件", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key="image_uploader")
                for f in files:
                    uploaded_files.append((f.name, f.getvalue()))
            
            if uploaded_files:
                st.success(f"已加载 {len(uploaded_files)} 张图片")
                
                with st.expander("📷 图片预览", expanded=False):
                    cols = st.columns(4)
                    for idx, (name, data) in enumerate(uploaded_files[:8]):
                        with cols[idx % 4]:
                            st.image(data, caption=name, use_container_width=True)
        
        # 产品货号
        st.subheader("产品信息")
        style_code = st.text_input("产品货号", value="DDD-341")
        
        # 处理按钮
        if st.button("🚀 开始处理", type="primary"):
            if template_df is None:
                st.error("请先选择或上传模板")
            elif not uploaded_files:
                st.error("请上传图片")
            elif not style_code:
                st.error("请输入产品货号")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 解析图片
                status_text.text("📋 解析图片文件名...")
                images = {}
                for name, data in uploaded_files:
                    sc, img_num = parse_filename(name)
                    if sc not in images:
                        images[sc] = {}
                    images[sc][img_num] = (name, data)
                
                # 使用第一个款号的图片
                first_style = list(images.keys())[0]
                style_images = images[first_style]
                
                st.info(f"识别到图片: {list(style_images.keys())}")
                
                # 上传图片
                status_text.text("☁️ 上传图片到图床...")
                image_urls = {}
                total = len(style_images)
                processed = 0
                
                for img_num, (filename, data) in style_images.items():
                    processed += 1
                    progress_bar.progress(processed / total / 2)
                    status_text.text(f"☁️ 上传中 {processed}/{total}: {filename}")
                    
                    url = upload_to_imgbb(data, imgbb_key)
                    if url:
                        image_urls[img_num] = url
                
                status_text.text(f"✅ 上传完成: {len(image_urls)}/{total} 张")
                
                # 构建图片URL列表
                carousel_urls = [image_urls[n] for n in rules["carousel_range"] if n in image_urls]
                detail_urls = [image_urls[n] for n in rules["detail_range"] if n in image_urls]
                material_url = image_urls.get(rules["material_image"], "")
                
                # 生成新产品数据
                status_text.text("📊 生成产品数据...")
                template_row = template_df.iloc[0].to_dict()
                new_products = []
                
                for img_num, config in rules["size_mapping"].items():
                    if img_num not in image_urls:
                        continue
                    
                    product = template_row.copy()
                    
                    # 更新基本信息
                    product['产品货号'] = style_code
                    product['变种名称'] = config['size']
                    product['变种属性值一'] = config['size']
                    product['申报价格'] = config['price']
                    product['SKU货号'] = f"{style_code}-{config['size']}"
                    product['长'] = config['length']
                    product['宽'] = config['width']
                    product['高'] = config['height']
                    product['重量'] = config['weight']
                    
                    # 更新图片
                    product['预览图'] = image_urls[img_num]
                    product['轮播图'] = '\n'.join(carousel_urls)
                    product['产品素材图'] = material_url
                    
                    # 产品描述
                    detail_html = '<br>'.join([f'<img src="{url}"/>' for url in detail_urls])
                    product['产品描述'] = detail_html
                    
                    # SKC属性
                    try:
                        skc_data = json.loads(template_row.get('SKC属性', '[]'))
                        if skc_data:
                            skc_data[0]['previewImgUrls'] = image_urls[img_num]
                            skc_data[0]['extCode'] = style_code
                        product['SKC属性'] = json.dumps(skc_data, ensure_ascii=False)
                    except:
                        pass
                    
                    # SKU属性
                    try:
                        sku_data = json.loads(template_row.get('SKU属性', '[]'))
                        if sku_data:
                            sku_data[0]['specName'] = config['size']
                        product['SKU属性'] = json.dumps(sku_data, ensure_ascii=False)
                    except:
                        pass
                    
                    # 清空ID字段
                    product['SPUID'] = ''
                    product['SKCID'] = ''
                    product['SKUID'] = ''
                    product['创建时间'] = ''
                    product['更新时间'] = ''
                    
                    new_products.append(product)
                
                # 生成Excel
                result_df = pd.DataFrame(new_products)
                
                progress_bar.progress(1.0)
                status_text.text("✅ 处理完成！")
                
                st.success(f"🎉 成功生成 {len(new_products)} 个产品变种")
                
                # 提供下载
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_buffer = BytesIO()
                result_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 下载Excel文件",
                    data=excel_buffer,
                    file_name=f"店小秘导入_{style_code}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # 询问是否保存为模板
                if template_source == "上传新模板" and template_name:
                    if st.button("💾 保存此模板"):
                        template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.xlsx")
                        template_df.to_excel(template_path, index=False, engine='openpyxl')
                        st.success(f"模板已保存: {template_name}")
                        st.rerun()
    
    # ========== 模板管理 ==========
    with tab2:
        st.header("📚 已保存的模板")
        
        templates = get_templates()
        
        if templates:
            for name, path in templates.items():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📄 **{name}**")
                    df = pd.read_excel(path)
                    st.caption(f"变种数量: {len(df)}, 尺寸: {', '.join(df['变种属性值一'].tolist())}")
                with col2:
                    # 下载模板
                    with open(path, 'rb') as f:
                        st.download_button("下载", f, file_name=f"{name}.xlsx", key=f"dl_{name}")
                with col3:
                    if st.button("🗑️ 删除", key=f"del_{name}"):
                        os.remove(path)
                        st.success(f"已删除: {name}")
                        st.rerun()
                st.markdown("---")
        else:
            st.info("暂无已保存的模板。在「模板处理」页面上传新模板时可选择保存。")
    
    # ========== 使用说明 ==========
    with tab3:
        st.header("使用说明")
        
        st.markdown("""
        ### 📝 工作流程
        
        1. **准备模板**
           - 从店小秘导出一个已上架产品的Excel作为模板
           - 模板包含所有固定属性（材质、克重、运费模板等）
           
        2. **上传模板**
           - 在「模板处理」页面上传模板Excel
           - 可选择保存模板供后续使用
           
        3. **上传图片**
           - 图片命名格式：`款号-编号.jpg`（如 `DDD-341-01.jpg`）
           - 或 PS导出格式：`未标题-1(1)_01.jpg`
           
        4. **输入产品货号**
           - 填写新的产品货号
           
        5. **生成Excel**
           - 点击「开始处理」
           - 下载生成的Excel文件
           - 导入店小秘
        
        ---
        
        ### 📏 默认尺寸配置
        
        | 图片编号 | 尺寸 | 价格 | 长×宽×高 | 重量 |
        |---------|------|------|---------|------|
        | 01 | 40*60cm | 150元 | 60×40×3cm | 200g |
        | 02 | 40*120cm | 200元 | 122×40×3cm | 300g |
        | 04 | 80*120cm | 250元 | 120×80×3cm | 800g |
        | 05 | 160*180cm | 400元 | 160×38×38cm | 2000g |
        
        可在左侧配置栏自定义修改。
        
        ---
        
        ### 🖼️ 图片用途配置
        
        | 用途 | 默认编号 |
        |------|---------|
        | 轮播图 | 01-10 |
        | 详情图 | 03-10 |
        | 产品素材图 | 01 |
        | 各尺寸预览图 | 01/02/04/05 |
        
        可在左侧配置栏自定义修改。
        
        ---
        
        ### 💡 注意事项
        
        - 图片编号必须为两位数字（01, 02, ...）
        - 产品货号会用于SKU货号和SKC属性
        - 首次使用请确认ImgBB API Key是否有效
        """)

if __name__ == "__main__":
    main()
