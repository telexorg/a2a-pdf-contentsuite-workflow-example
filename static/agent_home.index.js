const form = document.getElementById("testForm");
const responseBox = document.getElementById("response");
const fileInput = document.getElementById("fileInput");
const fileUploadArea = document.getElementById("fileUploadArea");
const fileList = document.getElementById("fileList");

let selectedFiles = [];
let currentEventSource = null; // Track current SSE connection

// === File Upload Handling ===

fileUploadArea.addEventListener("click", () => fileInput.click());

["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  fileUploadArea.addEventListener(eventName, preventDefaults, false);
  document.body.addEventListener(eventName, preventDefaults, false);
});

["dragenter", "dragover"].forEach((eventName) =>
  fileUploadArea.addEventListener(eventName, () =>
    fileUploadArea.classList.add("dragover")
  )
);
["dragleave", "drop"].forEach((eventName) =>
  fileUploadArea.addEventListener(eventName, () =>
    fileUploadArea.classList.remove("dragover")
  )
);

fileUploadArea.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  handleFiles(files);
});

fileInput.addEventListener("change", (e) => {
  handleFiles(e.target.files);
});

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function handleFiles(files) {
  [...files].forEach((file) => {
    if (!selectedFiles.find((f) => f.name === file.name && f.size === file.size)) {
      selectedFiles.push(file);
    }
  });
  updateFileList();
}

function updateFileList() {
  fileList.innerHTML = selectedFiles
    .map(
      (file, index) => `
      <div class="file-item">
        <span class="file-name">${file.name}</span>
        <span class="file-size">${formatFileSize(file.size)}</span>
        <button type="button" class="remove-file" onclick="removeFile(${index})">×</button>
      </div>`
    )
    .join("");
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  updateFileList();
}

function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = (error) => reject(error);
  });
}

// === SSE Response Handling ===

function handleSSEResponse(data) {
  try {
    // Handle different types of SSE data
    if (data.error) {
      const errorMsg = data.error.message || JSON.stringify(data.error);
      responseBox.textContent += `Error: ${errorMsg}\n`;
      return;
    }

    if (data.text) {
      // Direct text content
      responseBox.textContent += data.text;
    } else if (data.parts) {
      // Handle message parts (if the response has parts structure)
      data.parts.forEach(part => {
        if (part.text) {
          responseBox.textContent += part.text;
        } else if (part.type === 'text' && part.content) {
          responseBox.textContent += part.content;
        }
      });
    } else if (data.content) {
      // Handle direct content field
      responseBox.textContent += data.content;
    } else if (data.message) {
      // Handle message field
      responseBox.textContent += data.message;
    } else if (typeof data === 'string') {
      // Handle raw string data
      responseBox.textContent += data;
    } else {
      // For debugging - show the raw JSON structure
      console.log('Received SSE data:', data);
      // Try to extract any text content from unknown structure
      const jsonStr = JSON.stringify(data, null, 2);
      responseBox.textContent += `[Data: ${jsonStr}]\n`;
    }
  } catch (error) {
    console.error('Error handling SSE data:', error);
    responseBox.textContent += `\n[Error processing response data]\n`;
  }
}

function connectToStream(streamId) {
  // Close any existing connection
  if (currentEventSource) {
    currentEventSource.close();
  }

  const streamUrl = `/request-handler/stream/${streamId}`;
  console.log('Connecting to stream:', streamUrl);
  
  currentEventSource = new EventSource(streamUrl);

  currentEventSource.onopen = function(event) {
    console.log('SSE connection opened');
  };

  currentEventSource.onmessage = function(event) {
    try {
      const data = JSON.parse(event.data);
      
      if (data.final) {
        console.log('Stream completed');
        currentEventSource.close();
        currentEventSource = null;
        return;
      }
      
      handleSSEResponse(data);
    } catch (error) {
      console.error('Error parsing SSE message:', error);
      console.log('Raw event data:', event.data);
      // Try to display the raw data
      responseBox.textContent += `[Raw: ${event.data}]\n`;
    }
  };

  currentEventSource.onerror = function(event) {
    console.error('SSE error:', event);
    responseBox.textContent += '\n[Connection error occurred]\n';
    currentEventSource.close();
    currentEventSource = null;
  };
}

// === Request Submission Logic ===

async function submitToBackend(text, agentId, files) {
  const filesPayload = [];

  for (const file of files) {
    try {
      const base64Data = await fileToBase64(file);
      filesPayload.push({
        name: file.name,
        mimeType: file.type || "application/octet-stream",
        bytes: base64Data,
      });
    } catch (error) {
      console.error(`Error converting ${file.name}:`, error);
      responseBox.textContent += `Error converting file ${file.name}: ${error.message}\n`;
    }
  }

  const payload = {
    text,
    agent_id: agentId,
    files: filesPayload,
  };

  try {
    // Step 1: Submit the request and get stream ID
    console.log('Submitting request...');
    const response = await fetch("/request-handler/submit/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('Submit response:', result);

    if (!result.stream_id) {
      throw new Error('No stream_id received from server');
    }

    // Clear response box and show it
    responseBox.style.display = "block";
    responseBox.textContent = "";

    // Step 2: Connect to the SSE stream
    connectToStream(result.stream_id);

  } catch (error) {
    console.error("Submission error:", error);
    responseBox.style.display = "block";
    responseBox.textContent = `Error: ${error.message}`;
  }
}

// === Form Event Handler ===

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const message = document.getElementById("message").value;
  const mode = document.getElementById("mode").value;
  const agentId = window.location.pathname.replaceAll("\/", "");

  await submitToBackend(message, agentId, selectedFiles);
});

// === Cleanup on page unload ===
window.addEventListener('beforeunload', () => {
  if (currentEventSource) {
    currentEventSource.close();
  }
});