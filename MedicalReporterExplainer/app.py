# medical_report_explainer.py
from flask import Flask, request, render_template_string, jsonify
import google.generativeai as genai
import os
import docx
from PIL import Image
import pytesseract
from pdfminer.high_level import extract_text
from pdf2image import convert_from_path
from datetime import datetime

app = Flask(__name__)

# Gemini API Key
API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=API_KEY)

# Tesseract OCR Path
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

explains_history = []

# ----- Text Extraction Functions -----
def extract_pdf_text(file_path, ocr_lang="eng"):
    try:
        text = extract_text(file_path)
        if text.strip(): return text
        images = convert_from_path(file_path, first_page=1, last_page=1)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang=ocr_lang, config='--psm 6') + "\n"
        return ocr_text if ocr_text.strip() else "⚠️ No readable text found."
    except Exception as e:
        return f"⚠️ Error extracting PDF text: {str(e)}"

def extract_docx_text(file_path):
    try:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        return f"⚠️ Error extracting DOCX: {str(e)}"

def extract_image_text(file_path, ocr_lang="eng"):
    try:
        image = Image.open(file_path)
        image.thumbnail((1000, 1000))
        text = pytesseract.image_to_string(image, lang=ocr_lang, config='--psm 6')
        return text if text.strip() else "⚠️ OCR did not detect any text."
    except Exception as e:
        return f"⚠️ OCR error: {str(e)}"

# ----- Routes -----
@app.route("/", methods=["GET"])
def index():
    return render_template_string(html_code, explains_history=explains_history)

@app.route("/process", methods=["POST"])
def process():
    explanation = ""
    error_msg = ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text_input = request.form.get("text_input")
    uploaded_file = request.files.get("file")
    input_lang = request.form.get("input_lang") or "English"
    output_lang = request.form.get("output_lang") or "English"
    summary_length = request.form.get("summary_length", "medium")

    ocr_lang_map = {
        "English": "eng", "Hindi": "hin", "French": "fra", "Spanish": "spa",
        "German": "deu", "Chinese": "chi_sim", "Japanese": "jpn"
    }
    ocr_lang = ocr_lang_map.get(input_lang, "eng")

    extracted_text = ""
    if uploaded_file:
        file_ext = os.path.splitext(uploaded_file.filename)[1].lower()
        valid_extensions = {'.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'}
        if file_ext not in valid_extensions:
            error_msg = f"⚠️ Unsupported file type: {file_ext}"
        else:
            file_path = os.path.join("Uploads", uploaded_file.filename)
            try:
                uploaded_file.save(file_path)
                if file_ext == '.pdf': extracted_text = extract_pdf_text(file_path, ocr_lang)
                elif file_ext == '.docx': extracted_text = extract_docx_text(file_path)
                elif file_ext == '.txt': extracted_text = open(file_path,"r",encoding="utf-8").read()
                elif file_ext in {'.png','.jpg','.jpeg'}: extracted_text = extract_image_text(file_path, ocr_lang)
            finally:
                if os.path.exists(file_path): os.remove(file_path)
    elif text_input:
        extracted_text = text_input

    if extracted_text.strip() and not extracted_text.startswith("⚠️"):
        try:
            length_map = {
                "short": "brief (3-4 bullet points)",
                "medium": "moderate length (5-7 bullet points)",
                "long": "detailed (10+ bullet points)"
            }
            length_description = length_map.get(summary_length, "moderate length (5-7 bullet points)")

            model = genai.GenerativeModel("gemini-flash-latest")
            response = model.generate_content(
                f"Explain the following medical report in {output_lang} in {length_description} with simple language and highlights:\n\n{extracted_text}"
            )
            explanation = response.text
            explains_history.append({
                "timestamp": timestamp,
                "explanation": explanation,
                "language": output_lang
            })
            if len(explains_history) > 5: explains_history.pop(0)
        except Exception as e:
            error_msg = f"⚠️ Explanation error: {str(e)}"
    elif extracted_text.startswith("⚠️"):
        error_msg = extracted_text

    return jsonify({
        "explanation": explanation,
        "error_msg": error_msg,
        "explains_history": explains_history
    })

@app.route("/clear_history", methods=["POST"])
def clear_history():
    explains_history.clear()
    return jsonify({"explains_history": explains_history})

# ----- HTML + CSS + JS -----
html_code = """ 
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🩺 Medical Report Explainer</title>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
<style>
body { font-family:'Roboto',sans-serif; margin:0; padding:0; background:#f0f8ff; transition:0.3s; }
#particles-js { position:fixed; top:0; left:0; width:100%; height:100vh; z-index:-1; }
.container { max-width:900px; margin:50px auto; padding:30px; background:rgba(255,255,255,0.95); border-radius:20px; box-shadow:0 15px 40px rgba(0,0,0,0.15); }
h2 { text-align:center; color:#ff4081; font-size:2.2em; margin-bottom:25px; animation:fadeIn 1s ease-in; }
h2::before { content:'🩺'; margin-right:8px; display:inline-block; animation:spinGlobe 10s linear infinite; }
textarea,input[type=file],select { width:100%; padding:14px; margin-bottom:15px; border-radius:12px; border:none; box-shadow:0 5px 15px rgba(0,0,0,0.1); font-size:1em; transition:0.3s; }
textarea:focus,input[type=file]:focus,select:focus { outline:none; transform:translateY(-2px); box-shadow:0 8px 20px rgba(43,108,176,0.3); }
button { padding:14px 28px; font-weight:600; border:none; border-radius:12px; cursor:pointer; background:linear-gradient(135deg,#ff6ec4,#42a5f5); color:#fff; font-size:1em; transition:all 0.3s; }
button:hover { transform:translateY(-3px); box-shadow:0 8px 25px rgba(0,0,0,0.3); }
#spinner { display:none; border:4px solid rgba(255,255,255,0.3); border-top:4px solid #42a5f5; border-radius:50%; width:30px; height:30px; animation:spin 1s linear infinite; margin:20px auto; }
#explanationBox { display:none; padding:20px; border-radius:15px; background:#e0f7fa; margin-top:20px; animation:fadeInUp 0.8s ease-out; box-shadow:0 8px 25px rgba(0,0,0,0.2); }
#explanationText span { display:block; font-weight:500; font-size:1em; background: linear-gradient(-45deg,#ff6ec4,#42a5f5,#ffea00,#ff4081); -webkit-background-clip:text; -webkit-text-fill-color:transparent; animation:colorShift 3s ease infinite; margin-bottom:5px; }
#errorBox { display:none; padding:20px; border-radius:15px; background:#ffe0e0; margin-top:20px; color:#b71c1c; }
.history-box { display:none; margin-top:20px; max-height:300px; overflow-y:auto; }
.history-item { margin-bottom:15px; padding:15px; border-radius:15px; background:linear-gradient(135deg,#ffe57f,#ffd740); animation:fadeInUp 0.6s ease-out; box-shadow:0 8px 20px rgba(0,0,0,0.15); transition:transform 0.3s; }
.history-item:hover { transform:scale(1.03); }
@keyframes fadeIn { from{opacity:0;} to{opacity:1;} }
@keyframes fadeInUp { from{opacity:0; transform:translateY(20px);} to{opacity:1; transform:translateY(0);} }
@keyframes spinGlobe { from{transform:rotate(0deg);} to{transform:rotate(360deg);} }
@keyframes spin { 0%{transform:rotate(0deg);} 100%{transform:rotate(360deg);} }
@keyframes colorShift { 0%{background-position:0% 50%;} 50%{background-position:100% 50%;} 100%{background-position:0% 50%;} background-size:200% 200%; }
</style>
</head>
<body>
<div id="particles-js"></div>
<div class="container">
<h2>Medical Report Explainer</h2>
<form id="uploadForm" enctype="multipart/form-data">
<textarea name="text_input" rows="5" placeholder="Paste medical report here..."></textarea>
<input type="file" name="file" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg">
<select name="input_lang">
<option selected>English</option><option>Hindi</option><option>French</option><option>Spanish</option>
<option>German</option><option>Chinese</option><option>Japanese</option>
</select>
<select name="output_lang">
<option selected>English</option><option>Hindi</option><option>French</option><option>Spanish</option>
<option>German</option><option>Chinese</option><option>Japanese</option>
</select>
<select name="summary_length">
<option value="short" selected>Short</option>
<option value="medium">Medium</option>
<option value="long">Long</option>
</select>
<button type="submit">Explain Report</button>
<div id="spinner"></div>
</form>

<div id="explanationBox"><h3>📝 Explanation</h3><div id="explanationText"></div></div>
<div id="errorBox"><h3>⚠️ Error</h3><p id="errorText"></p></div>
<div class="history-box" id="historyBox"><h3>📜 Recent Explanations</h3><div id="historyContent"></div></div>
</div>

<script>
particlesJS('particles-js', { particles:{number:{value:90,density:{enable:true,value_area:900}},color:{value:'#ffffff'},shape:{type:'circle'},opacity:{value:0.5,random:true},size:{value:4,random:true},line_linked:{enable:true,distance:180,color:'#fff',opacity:0.25,width:1},move:{enable:true,speed:2,direction:'none',random:true,out_mode:'out'}},interactivity:{detect_on:'canvas',events:{onhover:{enable:true,mode:'repulse'},onclick:{enable:true,mode:'push'},resize:true},modes:{repulse:{distance:120,duration:0.4},push:{particles_nb:4}}},retina_detect:true});

const form=document.getElementById('uploadForm');
const explanationBox=document.getElementById('explanationBox');
const explanationText=document.getElementById('explanationText');
const errorBox=document.getElementById('errorBox');
const errorText=document.getElementById('errorText');
const spinner=document.getElementById('spinner');
const historyBox=document.getElementById('historyBox');
const historyContent=document.getElementById('historyContent');

form.addEventListener('submit',async e=>{
e.preventDefault();
explanationBox.style.display='none';
errorBox.style.display='none';
spinner.style.display='block';
const formData=new FormData(form);
try{
const response=await fetch('/process',{method:'POST',body:formData});
const data=await response.json();
spinner.style.display='none';

if(data.error_msg){errorText.textContent=data.error_msg; errorBox.style.display='block';}
else if(data.explanation){
explanationText.innerHTML='';
data.explanation.split('\\n').forEach(line=>{
const span=document.createElement('span'); span.textContent=line; explanationText.appendChild(span);
});
explanationBox.style.display='block';
}

historyContent.innerHTML='';
data.explains_history.forEach(item=>{
const div=document.createElement('div'); div.className='history-item';
div.innerHTML=`<p><b>Time:</b> ${item.timestamp} | <b>Language:</b> ${item.language}</p><p>${item.explanation}</p>`;
historyContent.appendChild(div);
});
historyBox.style.display=data.explains_history.length?'block':'none';
}catch(err){spinner.style.display='none'; errorText.textContent='⚠️ Network error.'; errorBox.style.display='block';}
});
</script>
</body>
</html>
"""

if __name__=="__main__":
    os.makedirs("Uploads", exist_ok=True)
    app.run(debug=True)
