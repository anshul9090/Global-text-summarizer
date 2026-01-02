from flask import Flask, request, jsonify
import google.generativeai as genai
import os
import docx
from PIL import Image
import pytesseract
from pdfminer.high_level import extract_text
from pdf2image import convert_from_path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import logging
import tempfile

# -------------------- App --------------------
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------- Gemini API --------------------
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY not set in environment variables")

client = genai.Client(api_key=API_KEY)

# -------------------- OCR --------------------
pytesseract.pytesseract.tesseract_cmd = "tesseract"

# -------------------- Memory --------------------
summaries_history = []

# -------------------- Helpers --------------------
def extract_pdf_text(path):
    try:
        text = extract_text(path)
        if text.strip():
            return text

        images = convert_from_path(path, first_page=1, last_page=1)
        return "".join(pytesseract.image_to_string(img) for img in images)

    except Exception as e:
        logging.error(e)
        return f"PDF error: {e}"

def extract_docx_text(path):
    try:
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logging.error(e)
        return f"DOCX error: {e}"

def extract_image_text(path):
    try:
        img = Image.open(path)
        return pytesseract.image_to_string(img)
    except Exception as e:
        logging.error(e)
        return f"OCR error: {e}"

# -------------------- Routes --------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Global Text Summarizer API running"})

@app.route("/process", methods=["POST"])
def process():
    extracted_text = ""
    summary = ""
    error = ""

    text_input = request.form.get("text")
    url_input = request.form.get("url")
    file = request.files.get("file")

    output_lang = request.form.get("output_lang", "English")
    summary_length = request.form.get("summary_length", "Medium")

    length_map = {"Short": 100, "Medium": 200, "Long": 300}
    word_limit = length_map.get(summary_length, 200)

    # ---------- File ----------
    if file:
        suffix = os.path.splitext(file.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            path = tmp.name

        try:
            if suffix == ".pdf":
                extracted_text = extract_pdf_text(path)
            elif suffix == ".docx":
                extracted_text = extract_docx_text(path)
            elif suffix in [".png", ".jpg", ".jpeg"]:
                extracted_text = extract_image_text(path)
            elif suffix == ".txt":
                with open(path, "r", encoding="utf-8") as f:
                    extracted_text = f.read()
            else:
                error = "Unsupported file type"
        finally:
            os.remove(path)

    # ---------- URL ----------
    elif url_input:
        try:
            res = requests.get(url_input, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")
            extracted_text = soup.get_text(separator="\n")
        except Exception as e:
            error = f"URL error: {e}"

    # ---------- Text ----------
    elif text_input:
        extracted_text = text_input

    else:
        error = "No input provided"

    # ---------- Gemini Summarization ----------
    if extracted_text and not error:
        try:
            response = client.generate_text(
                model="gemini-1.5-turbo",
                prompt=f"Summarize in {output_lang} within {word_limit} words:\n\n{extracted_text}",
                max_output_tokens=word_limit * 2
            )

            summary = response.text

            summaries_history.append({
                "time": datetime.now().isoformat(),
                "summary": summary
            })

            # Keep last 5 summaries
            summaries_history[:] = summaries_history[-5:]

        except Exception as e:
            logging.error(e)
            error = f"Gemini error: {e}"

    return jsonify({
        "summary": summary,
        "error": error,
        "history": summaries_history
    })

@app.route("/clear", methods=["POST"])
def clear():
    summaries_history.clear()
    return jsonify({"status": "history cleared"})

# -------------------- Render Entry --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)



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
      e.preventDefault();
      const formData = new FormData(form);
      summaryBox.style.display = 'none';
      errorBox.style.display = 'none';
      fileContainer.classList.add('processing');

      try {
        const response = await fetch('/process', {
          method: 'POST',
          body: formData
        });
        const data = await response.json();

        fileContainer.classList.remove('processing');
        fileContainerText.textContent = 'Click to select a file';
        fileInput.value = ''; // Clear file input

        if (data.error_msg) {
          errorText.textContent = data.error_msg;
          errorBox.style.display = 'block';
          errorBox.style.animation = 'fadeInUp 0.6s ease-out';
        } else if (data.summary) {
          summaryText.textContent = data.summary;
          summaryBox.style.display = 'block';
          summaryBox.style.animation = 'fadeInUp 0.6s ease-out';
        }

        // Update history
        historyContent.innerHTML = '';
        data.summaries_history.forEach(item => {
          const historyItem = document.createElement('div');
          historyItem.className = 'history-item';
          historyItem.innerHTML = `
            <p><b>Time:</b> ${item.timestamp} | <b>Language:</b> ${item.language} | <b>Length:</b> ${item.length} | <b>Format:</b> ${item.format}</p>
            <p>${item.summary}</p>
          `;
          historyContent.appendChild(historyItem);
        });
      } catch (error) {
        fileContainer.classList.remove('processing');
        fileContainerText.textContent = 'Click to select a file';
        fileInput.value = '';
        errorText.textContent = '⚠️ Network error: Unable to process request.';
        errorBox.style.display = 'block';
        errorBox.style.animation = 'fadeInUp 0.6s ease-out';
      }
    });

    // Handle clear history via AJAX
    clearHistoryBtn.addEventListener('click', async () => {
      try {
        const response = await fetch('/clear_history', {
          method: 'POST'
        });
        const data = await response.json();
        historyContent.innerHTML = '';
        historyBox.style.display = 'none';
        toggleHistoryBtn.textContent = '📜 Show History';
      } catch (error) {
        errorText.textContent = '⚠️ Network error: Unable to clear history.';
        errorBox.style.display = 'block';
        errorBox.style.animation = 'fadeInUp 0.6s ease-out';
      }
    });

    toggleHistoryBtn.addEventListener('click', () => {
      if (historyBox.style.display === 'none' || historyBox.style.display === '') {
        historyBox.style.display = 'block';
        historyBox.style.animation = 'fadeInUp 0.6s ease-out';
        toggleHistoryBtn.textContent = '📜 Hide History';
      } else {
        historyBox.style.animation = 'fadeInUp 0.6s ease-out reverse';
        setTimeout(() => { historyBox.style.display = 'none'; }, 600);
        toggleHistoryBtn.textContent = '📜 Show History';
      }
    });

    toggleThemeBtn.addEventListener('click', () => {
      body.classList.toggle('dark-mode');
      toggleThemeBtn.textContent = body.classList.contains('dark-mode') ? '☀️ Light Mode' : '🌙 Dark Mode';
      particlesJS('particles-js', {
        particles: {
          number: { value: 80, density: { enable: true, value_area: 800 } },
          color: { value: body.classList.contains('dark-mode') ? '#a0aec0' : '#e2e8f0' },
          shape: { type: 'circle' },
          opacity: { value: 0.4, random: true },
          size: { value: 3, random: true },
          line_linked: { enable: true, distance: 150, color: body.classList.contains('dark-mode') ? '#a0aec0' : '#e2e8f0', opacity: 0.3, width: 1 },
          move: { enable: true, speed: 2, direction: 'none', random: true, out_mode: 'out' }
        },
        interactivity: {
          detect_on: 'canvas',
          events: { onhover: { enable: true, mode: 'repulse' }, onclick: { enable: true, mode: 'push' }, resize: true },
          modes: { repulse: { distance: 100, duration: 0.4 }, push: { particles_nb: 4 } }
        },
        retina_detect: true
      });
    });
  </script>
</body>
</html>
"""
os.makedirs("Uploads", exist_ok=True)
