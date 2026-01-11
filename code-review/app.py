import streamlit as st
import subprocess
import os
import threading
import queue
import time

st.set_page_config(page_title="Cline Code Review Agent", layout="wide")

st.title("🤖 Cline Code Review Agent")
st.markdown("Enter the repository URL and Pull Request ID to start an autonomous code review.")

# Input fields
pr_url = st.text_input("Pull Request URL", placeholder="https://github.com/owner/repo/pull/123")

# Prompt template
PROMPT_TEMPLATE = """
Please perform a comprehensive code review for the pull request: {pr_url}
Focus on:
1. Code quality and best practices
2. Potential bugs and security vulnerabilities
3. Performance improvements
Review the changes and provide constructive feedback.
"""

def run_cline_process(prompt, output_queue):
    """Runs the Cline CLI with the given prompt and streams output to a queue."""
    try:
        # Construct the command
        # Using --yolo for non-interactive mode as requested
        # echo "prompt" | cline --yolo
        command = f'echo "{prompt}" | cline --yolo'
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Read stdout and stderr in separate threads or sequential loops
        # Since we want to stream, we'll read line by line
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                output_queue.put(output)
        
        # Capture any remaining stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            output_queue.put(f"[STDERR] {stderr_output}")

        return_code = process.poll()
        output_queue.put(f"[PROCESS COMPLETED] Return Code: {return_code}")

    except Exception as e:
        output_queue.put(f"[ERROR] Failed to run Cline: {str(e)}")

# Session state for managing the process
if 'running' not in st.session_state:
    st.session_state.running = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'output_queue' not in st.session_state:
    st.session_state.output_queue = queue.Queue()

def start_review():
    if not pr_url:
        st.error("Please provide the Pull Request URL.")
        return
    
    st.session_state.running = True
    st.session_state.logs = []
    
    prompt = PROMPT_TEMPLATE.format(pr_url=pr_url)
    st.session_state.logs.append(f"Starting review for {pr_url}...\n")
    st.session_state.logs.append(f"Prompt:\n{prompt}\n")
    
    # Start the process in a separate thread to not block UI
    thread = threading.Thread(target=run_cline_process, args=(prompt, st.session_state.output_queue))
    thread.daemon = True
    thread.start()

if st.button("Start Review", disabled=st.session_state.running):
    start_review()

# Display logs
log_container = st.container()
with log_container:
    st.subheader("Execution Logs")
    # We use empty to be able to update it
    log_area = st.empty()

    # If running, consume queue and update logs
    if st.session_state.running:
        # Read all available items in queue
        while not st.session_state.output_queue.empty():
            try:
                line = st.session_state.output_queue.get_nowait()
                st.session_state.logs.append(line)
                if "[PROCESS COMPLETED]" in line:
                    st.session_state.running = False
            except queue.Empty:
                break
        
        # Refresh logs
        log_text = "".join(st.session_state.logs)
        log_area.code(log_text, language="bash")
        
        # Rerun to keep polling the queue if still running
        if st.session_state.running:
            time.sleep(0.5)
            st.rerun()
    else:
        # Show final logs
        if st.session_state.logs:
            log_text = "".join(st.session_state.logs)
            log_area.code(log_text, language="bash")
            st.success("Review process completed.")

