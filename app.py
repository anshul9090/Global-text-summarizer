from flask import Flask, request, render_template_string, jsonify
from google import genai
import os
from dotenv import load_dotenv
import docx
from PIL import Image
import pytesseract
from pdfminer.high_level import extract_text
from pdf2image import convert_from_path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import logging

# ---------------------- Setup ----------------------
app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise Exception("⚠️ Please set GEMINI_API_KEY in your .env file.")

# Create GenAI client
client = genai.Client(api_key=API_KEY)

# Tesseract OCR path
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
    logging.warning("Tesseract not found at default path. Install from https://github.com/UB-Mannheim/tesseract/wiki")

# History
summaries_history = []

# ---------------------- Helper Functions ----------------------
def extract_pdf_text(file_path, ocr_lang="eng"):
    try:
        text = extract_text(file_path)
        if text.strip():
            return text
        # OCR fallback for first page
        images = convert_from_path(file_path, first_page=1, last_page=1)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang=ocr_lang, config='--psm 6') + "\n"
        return ocr_text if ocr_text.strip() else "⚠️ No readable text found."
    except Exception as e:
        logging.error(f"PDF extraction error: {str(e)}")
        return f"⚠️ Error extracting PDF text: {str(e)}"

def extract_docx_text(file_path):
    try:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        logging.error(f"DOCX extraction error: {str(e)}")
        return f"⚠️ Error extracting DOCX: {str(e)}"

def extract_image_text(file_path, ocr_lang="eng"):
    try:
        img = Image.open(file_path)
        img.thumbnail((1000,1000))
        text = pytesseract.image_to_string(img, lang=ocr_lang, config='--psm 6')
        return text if text.strip() else "⚠️ OCR did not detect any text."
    except Exception as e:
        logging.error(f"OCR error: {str(e)}")
        return f"⚠️ OCR error: {str(e)}"

# ---------------------- Routes ----------------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(html_code, summary="", error_msg="", summaries_history=summaries_history)

@app.route("/process", methods=["POST"])
def process():
    summary = ""
    error_msg = ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text_input = request.form.get("text_input")
    url_input = request.form.get("url_input")
    uploaded_file = request.files.get("file")
    input_lang = request.form.get("input_lang") or "English"
    output_lang = request.form.get("output_lang") or "English"
    summary_length = request.form.get("summary_length") or "Medium"
    summary_format = request.form.get("summary_format") or "Paragraph"

    # Word limits
    length_map = {"Short": 100, "Medium": 200, "Long": 300}
    word_limit = length_map.get(summary_length, 200)
    format_prompt = "as a paragraph" if summary_format == "Paragraph" else "in bullet points"

    ocr_lang_map = {
        "English": "eng", "Hindi": "hin", "French": "fra", "Spanish": "spa",
        "German": "deu", "Chinese": "chi_sim", "Japanese": "jpn"
    }
    ocr_lang = ocr_lang_map.get(input_lang, "eng")

    extracted_text = ""
    if uploaded_file:
        valid_extensions = {'.pdf','.docx','.txt','.png','.jpg','.jpeg'}
        file_ext = os.path.splitext(uploaded_file.filename)[1].lower()
        if file_ext not in valid_extensions:
            error_msg = f"⚠️ Unsupported file type: {file_ext}"
        else:
            file_path = os.path.join("Uploads", uploaded_file.filename)
            os.makedirs("Uploads", exist_ok=True)
            uploaded_file.save(file_path)
            if file_ext == '.pdf':
                extracted_text = extract_pdf_text(file_path, ocr_lang)
            elif file_ext == '.docx':
                extracted_text = extract_docx_text(file_path)
            elif file_ext == '.txt':
                with open(file_path, "r", encoding="utf-8") as f:
                    extracted_text = f.read()
            elif file_ext in {'.png','.jpg','.jpeg'}:
                extracted_text = extract_image_text(file_path, ocr_lang)
            os.remove(file_path)
    elif url_input:
        try:
            headers = {"User-Agent":"GlobalTextSummarizerBot/1.0"}
            r = requests.get(url_input, headers=headers, timeout=5)
            r.raise_for_status()
            soup = BeautifulSoup(r.text,'html.parser')
            extracted_text = soup.get_text(separator="\n",strip=True)
        except Exception as e:
            error_msg = f"⚠️ Error fetching URL: {str(e)}"
    elif text_input:
        extracted_text = text_input

    if extracted_text.strip() and not extracted_text.startswith("⚠️"):
        try:
            # Use new GenAI client
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Summarize the following text in {output_lang} {format_prompt}. Keep it concise (~{word_limit} words max):\n\n{extracted_text}"
            )
            summary = response.text
            summaries_history.append({
                "timestamp": timestamp,
                "summary": summary,
                "language": output_lang,
                "length": summary_length,
                "format": summary_format
            })
            if len(summaries_history) > 5:
                summaries_history.pop(0)
        except Exception as e:
            error_msg = f"⚠️ Summarization failed: {str(e)}"

    return jsonify({
        "summary": summary,
        "error_msg": error_msg,
        "summaries_history": summaries_history
    })

@app.route("/clear_history", methods=["POST"])
def clear_history():
    summaries_history.clear()
    return jsonify({"summaries_history": summaries_history})
# ========== HTML Template ==========
html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🌍 Global Text Summarizer</title>
  <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Roboto', sans-serif;
      margin: 0;
      padding: 0;
      color: #1a202c;
      background: none;
      overflow-x: hidden;
      transition: color 0.5s;
    }
    body.dark-mode {
      color: #e2e8f0;
    }
    #particles-js {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100vh;
      background: linear-gradient(135deg, #2b6cb0, #4a5568);
      z-index: -1;
    }
    body.dark-mode #particles-js {
      background: linear-gradient(135deg, #1a202c, #2d3748);
    }
    .container {
      max-width: 900px;
      margin: 40px auto;
      padding: 20px;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(12px);
      border-radius: 12px;
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
      animation: slideIn 0.8s ease-out;
      position: relative;
      z-index: 1;
    }
    body.dark-mode .container {
      background: rgba(45, 55, 72, 0.9);
    }
    h2 {
      text-align: center;
      font-size: 2em;
      margin-bottom: 15px;
      text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      animation: fadeIn 1.2s ease-in;
      color: #2b6cb0;
    }
    body.dark-mode h2 {
      color: #63b3ed;
    }
    h2::before {
      content: '🌍';
      display: inline-block;
      animation: spinGlobe 10s linear infinite;
      margin-right: 8px;
    }
    .button-container {
      text-align: center;
      margin-bottom: 15px;
    }
    form {
      opacity: 0;
      transform: translateX(-50px);
      animation: slideForm 0.6s ease-out forwards 0.4s;
    }
    label {
      font-weight: 500;
      margin-bottom: 8px;
      display: block;
      color: #2d3748;
      font-size: 0.9em;
    }
    body.dark-mode label {
      color: #e2e8f0;
    }
    textarea, input[type=text] {
      width: 100%;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: rgba(255, 255, 255, 0.95);
      color: #1a202c;
      font-size: 0.9em;
      transition: all 0.3s ease;
      box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05);
    }
    body.dark-mode textarea, body.dark-mode input[type=text] {
      background: rgba(45, 55, 72, 0.95);
      border-color: #4a5568;
      color: #e2e8f0;
    }
    textarea:focus, input[type=text]:focus {
      border-color: #2b6cb0;
      box-shadow: 0 3px 15px rgba(43, 108, 176, 0.3);
      outline: none;
    }
    select, input[type=file] {
      width: 100%;
      padding: 8px;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: rgba(255, 255, 255, 0.95);
      color: #1a202c;
      font-size: 0.9em;
      margin-top: 8px;
      transition: all 0.3s ease;
    }
    body.dark-mode select, body.dark-mode input[type=file] {
      background: rgba(45, 55, 72, 0.95);
      border-color: #4a5568;
      color: #e2e8f0;
    }
    button {
      padding: 10px 20px;
      border-radius: 8px;
      border: none;
      color: #fff;
      font-size: 1em;
      cursor: pointer;
      transition: all 0.3s ease;
      margin: 8px 4px;
      position: relative;
      overflow: hidden;
    }
    button.summarize-btn {
      background: linear-gradient(45deg, #2b6cb0, #4299e1);
    }
    body.dark-mode button.summarize-btn {
      background: linear-gradient(45deg, #2d3748, #4a5568);
    }
    button.action-btn {
      background: linear-gradient(45deg, #319795, #4fd1c5);
    }
    body.dark-mode button.action-btn {
      background: linear-gradient(45deg, #2c7a7b, #4a5568);
    }
    button::after {
      content: '';
      position: absolute;
      top: 50%;
      left: 50%;
      width: 0;
      height: 0;
      background: rgba(255, 255, 255, 0.3);
      border-radius: 50%;
      transform: translate(-50%, -50%);
      transition: width 0.4s ease, height 0.4s ease;
    }
    button:hover::after {
      width: 150px;
      height: 150px;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 15px rgba(0, 0, 0, 0.2);
    }
    .summary-box, .error-box, .history-box {
      margin-top: 15px;
      padding: 15px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.95);
      border-left: 4px solid #2b6cb0;
      box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
      animation: fadeInUp 0.6s ease-out;
    }
    body.dark-mode .summary-box, body.dark-mode .history-box {
      background: rgba(45, 55, 72, 0.95);
      border-left-color: #63b3ed;
    }
    .error-box {
      border-left-color: #e53e3e;
      color: #9b2c2c;
    }
    body.dark-mode .error-box {
      background: rgba(45, 55, 72, 0.95);
      color: #feb2b2;
    }
    .history-box {
      display: none;
      max-height: 300px;
      overflow-y: auto;
    }
    .history-item {
      margin-bottom: 10px;
      padding: 10px;
      background: rgba(237, 242, 247, 0.95);
      border-radius: 6px;
      transition: transform 0.3s ease;
    }
    body.dark-mode .history-item {
      background: rgba(74, 85, 104, 0.95);
    }
    .history-item:hover {
      transform: scale(1.02);
    }
    .file-input-container {
      border: 2px solid #2b6cb0;
      padding: 15px;
      text-align: center;
      margin-top: 8px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.95);
      transition: all 0.3s ease;
      position: relative;
    }
    body.dark-mode .file-input-container {
      background: rgba(45, 55, 72, 0.95);
      border-color: #63b3ed;
    }
    .file-input-container span {
      font-size: 0.85em;
      color: #2d3748;
      position: relative;
      z-index: 1;
    }
    body.dark-mode .file-input-container span {
      color: #e2e8f0;
    }
    .file-input-container.processing::after {
      content: 'Processing...';
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 0.9em;
      color: #2b6cb0;
      background: rgba(255, 255, 255, 0.8);
      padding: 8px 15px;
      border-radius: 6px;
      z-index: 2;
    }
    body.dark-mode .file-input-container.processing::after {
      color: #63b3ed;
      background: rgba(45, 55, 72, 0.8);
    }
    [data-tooltip] {
      position: relative;
    }
    [data-tooltip]:hover::after {
      content: attr(data-tooltip);
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translateX(-50%);
      background: #2d3748;
      color: #e2e8f0;
      padding: 6px 10px;
      border-radius: 5px;
      font-size: 0.8em;
      white-space: nowrap;
      z-index: 10;
      opacity: 0;
      transition: opacity 0.3s ease, transform 0.3s ease;
      transform: translateX(-50%) translateY(6px);
      pointer-events: none;
    }
    [data-tooltip]:hover::after {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }
    body.dark-mode [data-tooltip]:hover::after {
      background: #e2e8f0;
      color: #2d3748;
    }
    @keyframes slideIn {
      from { opacity: 0; transform: translateY(30px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(15px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes slideForm {
      from { opacity: 0; transform: translateX(-50px); }
      to { opacity: 1; transform: translateX(0); }
    }
    @keyframes spinGlobe {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .history-box::-webkit-scrollbar {
      width: 6px;
    }
    .history-box::-webkit-scrollbar-track {
      background: rgba(237, 242, 247, 0.95);
      border-radius: 8px;
    }
    .history-box::-webkit-scrollbar-thumb {
      background: #2b6cb0;
      border-radius: 8px;
    }
    body.dark-mode .history-box::-webkit-scrollbar-track {
      background: rgba(74, 85, 104, 0.95);
    }
    body.dark-mode .history-box::-webkit-scrollbar-thumb {
      background: #63b3ed;
    }
    .loader {
      display: none;
      border: 3px solid #e2e8f0;
      border-top: 3px solid #2b6cb0;
      border-radius: 50%;
      width: 16px;
      height: 16px;
      animation: spin 1s linear infinite;
      margin: 0 auto;
    }
    body.dark-mode .loader {
      border-color: #4a5568;
      border-top-color: #63b3ed;
    }
    .file-input-container.processing .loader {
      display: block;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div id="particles-js"></div>
  <div class="container">
    <h2>Global Text Summarizer</h2>
    <div class="button-container">
      <button type="button" id="toggleHistory" class="action-btn" data-tooltip="Show or hide recent summaries">📜 Show History</button>
      <button type="button" id="toggleTheme" class="action-btn" data-tooltip="Switch between light and dark themes">🌙 Dark Mode</button>
      <button type="button" id="clearHistory" class="action-btn" data-tooltip="Remove all previous summaries from history">🗑️ Clear History</button>
    </div>
    <form id="uploadForm" enctype="multipart/form-data">
      <label data-tooltip="Enter text to be summarized">Paste Text:</label>
      <textarea name="text_input" rows="4" placeholder="Paste text here..."></textarea>
      <label data-tooltip="Enter a URL to extract and summarize its content">Or Enter URL:</label>
      <input type="text" name="url_input" placeholder="https://example.com">
      <label data-tooltip="Upload a file (PDF, DOCX, TXT, PNG, JPG) to summarize">Or Upload a File:</label>
      <input type="file" name="file" id="fileInput" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg">
      <div class="file-input-container" id="fileContainer" data-tooltip="Click to select a file to summarize">
        <span id="fileContainerText">Click to select a file</span>
        <div class="loader"></div>
      </div>
      <label data-tooltip="Select the language of the input text for accurate OCR (used for images/PDFs)">Input Language (for OCR):</label>
      <select name="input_lang">
        <option selected>English</option>
        <option>Hindi</option>
        <option>French</option>
        <option>Spanish</option>
        <option>German</option>
        <option>Chinese</option>
        <option>Japanese</option>
      </select>
      <label data-tooltip="Select the language for the summary output">Choose Output Language:</label>
      <select name="output_lang">
        <option>English</option>
        <option>Hindi</option>
        <option>French</option>
        <option>Spanish</option>
        <option>German</option>
        <option>Chinese</option>
        <option>Japanese</option>
      </select>
      <label data-tooltip="Choose the desired length of the summary">Summary Length:</label>
      <select name="summary_length">
        <option>Short</option>
        <option selected>Medium</option>
        <option>Long</option>
      </select>
      <label data-tooltip="Choose the format of the summary output">Summary Format:</label>
      <select name="summary_format">
        <option>Paragraph</option>
        <option>Bullet points</option>
      </select>
      <div style="text-align: center;">
        <button type="submit" class="summarize-btn" data-tooltip="Generate a summary of the input text or file">✨ Summarize</button>
      </div>
    </form>

    <div id="summaryBox" class="summary-box" style="display: none;">
  <h3>📝 Summary</h3>
   <pre id="summaryText" style="white-space: pre-wrap; word-wrap: break-word;"></pre>
   </div>


    <div id="errorBox" class="error-box" style="display: none;">
      <h3>⚠️ Error</h3>
      <p id="errorText"></p>
    </div>

    <div class="history-box" id="historyBox">
      <h3>📜 Recent Summaries</h3>
      <div id="historyContent">
        {% for item in summaries_history %}
          <div class="history-item">
            <p><b>Time:</b> {{ item.timestamp }} | <b>Language:</b> {{ item.language }} | <b>Length:</b> {{ item.length }} | <b>Format:</b> {{ item.format }}</p>
            <p>{{ item.summary }}</p>
          </div>
        {% endfor %}
      </div>
    </div>
  </div>
<script>
  // Initialize particles.js
  particlesJS('particles-js', {
    particles: {
      number: { value: 80, density: { enable: true, value_area: 800 } },
      color: { value: '#e2e8f0' },
      shape: { type: 'circle' },
      opacity: { value: 0.4, random: true },
      size: { value: 3, random: true },
      line_linked: { enable: true, distance: 150, color: '#e2e8f0', opacity: 0.3, width: 1 },
      move: { enable: true, speed: 2, direction: 'none', random: true, out_mode: 'out' }
    },
    interactivity: {
      detect_on: 'canvas',
      events: { onhover: { enable: true, mode: 'repulse' }, onclick: { enable: true, mode: 'push' }, resize: true },
      modes: { repulse: { distance: 100, duration: 0.4 }, push: { particles_nb: 4 } }
    },
    retina_detect: true
  });

  const fileInput = document.getElementById('fileInput');
  const fileContainer = document.getElementById('fileContainer');
  const fileContainerText = document.getElementById('fileContainerText');
  const form = document.getElementById('uploadForm');
  const toggleHistoryBtn = document.getElementById('toggleHistory');
  const historyBox = document.getElementById('historyBox');
  const toggleThemeBtn = document.getElementById('toggleTheme');
  const clearHistoryBtn = document.getElementById('clearHistory');
  const summaryBox = document.getElementById('summaryBox');
  const summaryText = document.getElementById('summaryText');
  const errorBox = document.getElementById('errorBox');
  const errorText = document.getElementById('errorText');
  const historyContent = document.getElementById('historyContent');
  const body = document.body;

  // Handle file selection
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      const file = fileInput.files[0];
      const validExtensions = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg'];
      const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      if (!validExtensions.includes(fileExt)) {
        fileContainerText.textContent = 'Invalid file type! Please use PDF, DOCX, TXT, PNG, or JPG';
        fileContainer.style.borderColor = '#e53e3e';
        setTimeout(() => {
          fileContainerText.textContent = 'Click to select a file';
          fileContainer.style.borderColor = body.classList.contains('dark-mode') ? '#63b3ed' : '#2b6cb0';
          fileInput.value = '';
        }, 2000);
      } else {
        fileContainerText.textContent = `Selected: ${file.name}`;
      }
    } else {
      fileContainerText.textContent = 'Click to select a file';
    }
  });

  // Handle click on file container to trigger file input
  fileContainer.addEventListener('click', () => {
    fileInput.click();
  });

  // Handle form submission via AJAX
  form.addEventListener('submit', async (e) => {
    e.preventDefault(); // Prevent page reload

    summaryBox.style.display = 'none';
    errorBox.style.display = 'none';
    fileContainer.classList.add('processing');

    const formData = new FormData(form);

    try {
      const response = await fetch('/process', { method: 'POST', body: formData });
      const data = await response.json();

      fileContainer.classList.remove('processing');
      fileContainerText.textContent = 'Click to select a file';
      fileInput.value = '';

      if (data.error_msg) {
        errorText.textContent = data.error_msg;
        errorBox.style.display = 'block';
      } else if (data.summary) {
        summaryText.textContent = data.summary;
        summaryBox.style.display = 'block';
      }

      // Update history
      historyContent.innerHTML = '';
      data.summaries_history.forEach(item => {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        historyItem.innerHTML = `<p><b>Time:</b> ${item.timestamp} | <b>Language:</b> ${item.language} | <b>Length:</b> ${item.length} | <b>Format:</b> ${item.format}</p>
                                 <p>${item.summary}</p>`;
        historyContent.appendChild(historyItem);
      });
    } catch (error) {
      fileContainer.classList.remove('processing');
      fileContainerText.textContent = 'Click to select a file';
      fileInput.value = '';
      errorText.textContent = '⚠️ Network error: Unable to process request.';
      errorBox.style.display = 'block';
    }
  });

  // Handle clear history via AJAX
  clearHistoryBtn.addEventListener('click', async () => {
    try {
      const response = await fetch('/clear_history', { method: 'POST' });
      const data = await response.json();
      historyContent.innerHTML = '';
      historyBox.style.display = 'none';
      toggleHistoryBtn.textContent = '📜 Show History';
    } catch (error) {
      errorText.textContent = '⚠️ Network error: Unable to clear history.';
      errorBox.style.display = 'block';
    }
  });

  toggleHistoryBtn.addEventListener('click', () => {
    if (historyBox.style.display === 'none' || historyBox.style.display === '') {
      historyBox.style.display = 'block';
      toggleHistoryBtn.textContent = '📜 Hide History';
    } else {
      historyBox.style.display = 'none';
      toggleHistoryBtn.textContent = '📜 Show History';
    }
  });

  toggleThemeBtn.addEventListener('click', () => {
    body.classList.toggle('dark-mode');
    toggleThemeBtn.textContent = body.classList.contains('dark-mode') ? '☀️ Light Mode' : '🌙 Dark Mode';
  });
</script>

</body>
</html>
"""

if __name__ == "__main__":
    os.makedirs("Uploads", exist_ok=True)
    app.run(debug=True)