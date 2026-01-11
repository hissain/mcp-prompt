import streamlit as st
import subprocess
import os
import threading
import queue
import time
import json
import re

st.set_page_config(page_title="Cline Code Review Agent", layout="wide")

st.title("🤖 Cline Code Review Agent")
st.markdown("Enter the Pull Request URL to start an autonomous code review.")

# Input fields
pr_url = st.text_input("Pull Request URL", placeholder="https://github.com/owner/repo/pull/123")

# Prompt loading
PROMPT_FILE = "../agent_prompt.md"

def load_prompt():
    prompt_paths = [PROMPT_FILE, "agent_prompt.md", "../agent_prompt.md"]
    for path in prompt_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()
    return """Please perform a comprehensive code review for the pull request.
Focus on: 1. Code quality and best practices, 2. Potential bugs and security vulnerabilities, 3. Performance improvements"""

BASE_PROMPT = load_prompt()

def check_cline_config():
    """Check Cline configuration and return provider info"""
    try:
        result = subprocess.run(
            ["cline", "config", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse output to find provider and model
            output = result.stdout
            return True, output
        return False, "Could not read config"
    except Exception as e:
        return False, str(e)

def ensure_cline_instance():
    """Ensure a Cline instance is running"""
    try:
        result = subprocess.run(
            ["cline", "instance", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and ("localhost" in result.stdout or "127.0.0.1" in result.stdout):
            return True, "Instance already running"
        
        # Create new instance if none exists
        result = subprocess.run(
            ["cline", "instance", "new", "--default"],
            capture_output=True,
            text=True,
            timeout=20
        )
        
        if result.returncode != 0:
            return False, f"Failed to start instance: {result.stderr}"
        
        for i in range(10):
            time.sleep(1)
            check_result = subprocess.run(
                ["cline", "instance", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "localhost" in check_result.stdout or "127.0.0.1" in check_result.stdout:
                return True, f"Instance started (took {i+1}s)"
        
        return False, "Instance started but not responding"
        
    except Exception as e:
        return False, f"Error: {str(e)}"

def extract_rate_limit_info(error_text):
    """Extract rate limit information from error message"""
    retry_match = re.search(r'retry in (\d+\.?\d*)s', error_text, re.IGNORECASE)
    retry_seconds = float(retry_match.group(1)) if retry_match else 60
    
    info = {
        'retry_seconds': retry_seconds,
        'is_rate_limit': '429' in error_text or 'quota' in error_text.lower(),
        'is_quota_exceeded': 'quota exceeded' in error_text.lower()
    }
    return info

def run_cline_with_retry(prompt, output_queue, max_retries=3):
    """Run Cline with automatic retry on rate limits"""
    
    for attempt in range(max_retries):
        try:
            env = os.environ.copy()
            node_bin_path = "/Users/hissain/.nvm/versions/node/v22.18.0/bin"
            if node_bin_path not in env["PATH"]:
                env["PATH"] = f"{node_bin_path}:{env['PATH']}"
            
            if attempt > 0:
                output_queue.put(f"\n[RETRY] Attempt {attempt + 1} of {max_retries}...\n")
            
            output_queue.put("[INFO] Checking Cline instance...\n")
            instance_result = subprocess.run(
                ["cline", "instance", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                env=env
            )
            
            if "localhost" not in instance_result.stdout and "127.0.0.1" not in instance_result.stdout:
                output_queue.put("[ERROR] No Cline instance found.\n")
                output_queue.put("[PROCESS COMPLETED] Return Code: 1\n")
                return
            
            output_queue.put("[INFO] Starting review process...\n")
            
            command = ["cline", "--yolo", "--no-interactive"]
            
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
            )
            
            try:
                process.stdin.write(prompt)
                process.stdin.flush()
                process.stdin.close()
            except Exception as e:
                output_queue.put(f"[ERROR] Failed to send prompt: {e}\n")
                return
            
            output_queue.put("[INFO] Prompt sent, waiting for response...\n")
            
            start_time = time.time()
            timeout = 600
            
            full_output = []
            rate_limit_detected = False
            
            while True:
                if time.time() - start_time > timeout:
                    output_queue.put("[TIMEOUT] Process exceeded timeout\n")
                    process.kill()
                    break
                
                if process.poll() is not None:
                    break
                
                try:
                    line = process.stdout.readline()
                    if line:
                        output_queue.put(line)
                        full_output.append(line)
                        
                        # Detect rate limit
                        if '429' in line or 'quota' in line.lower():
                            rate_limit_detected = True
                except:
                    pass
                
                time.sleep(0.1)
            
            stdout, stderr = process.communicate(timeout=5)
            if stdout:
                output_queue.put(stdout)
                full_output.append(stdout)
            if stderr and stderr.strip():
                output_queue.put(f"[STDERR] {stderr}\n")
                full_output.append(stderr)
            
            return_code = process.returncode if process.returncode is not None else 1
            
            # Check if we should retry
            full_text = "".join(full_output)
            
            if rate_limit_detected and attempt < max_retries - 1:
                rate_info = extract_rate_limit_info(full_text)
                wait_time = int(rate_info['retry_seconds']) + 5
                
                output_queue.put(f"\n[RATE LIMIT] API quota exceeded. Waiting {wait_time}s before retry...\n")
                output_queue.put("[INFO] You may need to:\n")
                output_queue.put("  1. Wait for quota to reset\n")
                output_queue.put("  2. Check your API key at https://aistudio.google.com\n")
                output_queue.put("  3. Configure a different model: cline auth add\n\n")
                
                time.sleep(wait_time)
                continue  # Retry
            
            output_queue.put(f"\n[PROCESS COMPLETED] Return Code: {return_code}\n")
            return
            
        except Exception as e:
            output_queue.put(f"[ERROR] Exception: {str(e)}\n")
            if attempt < max_retries - 1:
                output_queue.put("[RETRY] Retrying in 10 seconds...\n")
                time.sleep(10)
            else:
                import traceback
                output_queue.put(f"[TRACEBACK] {traceback.format_exc()}\n")

# Session state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'output_queue' not in st.session_state:
    st.session_state.output_queue = queue.Queue()
if 'instance_checked' not in st.session_state:
    st.session_state.instance_checked = False
if 'instance_status' not in st.session_state:
    st.session_state.instance_status = None
if 'config_checked' not in st.session_state:
    st.session_state.config_checked = False
if 'config_info' not in st.session_state:
    st.session_state.config_info = None

# Check instance and config on first load
if not st.session_state.instance_checked:
    with st.spinner("Checking Cline setup..."):
        # Check instance
        success, message = ensure_cline_instance()
        st.session_state.instance_status = (success, message)
        st.session_state.instance_checked = True
        
        # Check config
        config_success, config_info = check_cline_config()
        st.session_state.config_info = config_info
        st.session_state.config_checked = True

# Display status
col1, col2 = st.columns(2)

with col1:
    st.subheader("Instance Status")
    if st.session_state.instance_status:
        success, message = st.session_state.instance_status
        if success:
            st.success(f"✅ {message}")
        else:
            st.error(f"❌ {message}")
            st.code("./fix_cline.sh", language="bash")

with col2:
    st.subheader("API Configuration")
    if st.session_state.config_info:
        with st.expander("View Configuration"):
            st.code(st.session_state.config_info, language="yaml")
    else:
        st.warning("⚠️ Could not read config")

def start_review():
    if not pr_url:
        st.error("Please provide the Pull Request URL.")
        return
    
    success, message = ensure_cline_instance()
    if not success:
        st.error(f"Cannot start: {message}")
        return
    
    st.session_state.running = True
    st.session_state.logs = []
    
    full_prompt = f"{BASE_PROMPT}\n\nTarget Pull Request URL: {pr_url}"
    st.session_state.logs.append(f"[START] Review for {pr_url}\n")
    st.session_state.logs.append("[INFO] Will auto-retry on rate limits\n\n")
    
    thread = threading.Thread(
        target=run_cline_with_retry,
        args=(full_prompt, st.session_state.output_queue, 3)
    )
    thread.daemon = True
    thread.start()

# Status
if st.session_state.running:
    st.info("🔄 Review in progress... Will auto-retry on rate limits.")

# Buttons
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("🚀 Start Review", disabled=st.session_state.running, type="primary"):
        start_review()

with col2:
    if st.button("🔄 Recheck"):
        success, message = ensure_cline_instance()
        st.session_state.instance_status = (success, message)
        config_success, config_info = check_cline_config()
        st.session_state.config_info = config_info
        st.rerun()

with col3:
    if st.button("🗑️ Clear"):
        st.session_state.logs = []
        st.session_state.running = False
        st.rerun()

# Help
with st.expander("💡 API Quota Issues?"):
    st.markdown("""
    ### If you see "429" or "quota exceeded":
    
    **Option 1: Wait**
    - Free tier resets quotas periodically
    - Wait time shown in error message
    - App will auto-retry
    
    **Option 2: Check Usage**
    - Visit: https://aistudio.google.com/app/apikey
    - Check your API usage/limits
    - Consider paid tier if needed
    
    **Option 3: Change Model**
    ```bash
    cline auth add --provider google
    # Select gemini-1.5-flash (faster, cheaper)
    ```
    
    **Option 4: Use Different Provider**
    ```bash
    # Anthropic Claude
    cline auth add --provider anthropic
    
    # OpenAI
    cline auth add --provider openai
    ```
    """)

# Logs
st.markdown("---")
st.subheader("📋 Review Logs")
log_area = st.empty()

if st.session_state.running:
    while not st.session_state.output_queue.empty():
        try:
            line = st.session_state.output_queue.get_nowait()
            st.session_state.logs.append(line)
            if "[PROCESS COMPLETED]" in line:
                st.session_state.running = False
        except queue.Empty:
            break
    
    log_text = "".join(st.session_state.logs)
    log_area.code(log_text, language="bash")
    
    if st.session_state.running:
        time.sleep(0.5)
        st.rerun()
else:
    if st.session_state.logs:
        log_text = "".join(st.session_state.logs)
        log_area.code(log_text, language="bash")
        
        if "Return Code: 0" in log_text:
            st.success("✅ Review completed!")
        elif "429" in log_text or "quota" in log_text.lower():
            st.warning("⚠️ Hit API rate limits. Consider waiting or changing models.")
        elif "Return Code: 1" in log_text:
            st.error("❌ Review failed. Check logs above.")
    else:
        log_area.info("No logs yet. Click 'Start Review' to begin.")
