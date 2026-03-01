// Chat input page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('update-form');
    const textInput = document.getElementById('update-text');
    const sendBtn = document.getElementById('send-btn');
    const attachBtn = document.getElementById('attach-btn');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewArea = document.getElementById('preview-area');
    const loading = document.getElementById('loading');
    const feed = document.getElementById('updates-feed');

    let selectedFiles = [];

    // Attach button toggles drop zone
    attachBtn.addEventListener('click', function() {
        dropZone.classList.toggle('hidden');
        if (!dropZone.classList.contains('hidden')) {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', function(e) {
        addFiles(Array.from(e.target.files));
    });

    // Drop zone events
    dropZone.addEventListener('click', function() {
        fileInput.click();
    });

    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.add('border-indigo-500', 'bg-indigo-50');
    });

    dropZone.addEventListener('dragleave', function() {
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
    });

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.classList.remove('border-indigo-500', 'bg-indigo-50');
        const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
        addFiles(files);
    });

    // Also allow drag-drop on the whole page
    document.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.remove('hidden');
    });

    function addFiles(files) {
        for (const file of files) {
            if (file.type.startsWith('image/')) {
                selectedFiles.push(file);
                showPreview(file);
            }
        }
    }

    function showPreview(file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const div = document.createElement('div');
            div.className = 'relative';
            div.innerHTML = `
                <img src="${e.target.result}" class="w-16 h-16 object-cover rounded border">
                <button type="button" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center"
                        onclick="this.parentElement.remove()">x</button>
            `;
            previewArea.appendChild(div);
        };
        reader.readAsDataURL(file);
    }

    // Form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        const text = textInput.value.trim();
        if (!text && selectedFiles.length === 0) return;

        // Disable UI
        sendBtn.disabled = true;
        loading.classList.remove('hidden');

        // Build FormData
        const formData = new FormData();
        formData.append('raw_text', text);
        formData.append('source', 'web');
        for (const file of selectedFiles) {
            formData.append('screenshots', file);
        }

        try {
            const resp = await fetch('/api/updates', {
                method: 'POST',
                body: formData
            });

            if (!resp.ok) {
                throw new Error('Server error: ' + resp.status);
            }

            const data = await resp.json();

            // Add to feed
            addUpdateToFeed(text, data, selectedFiles.length);

            // Clear input
            textInput.value = '';
            selectedFiles = [];
            previewArea.innerHTML = '';
            dropZone.classList.add('hidden');

        } catch(err) {
            alert('Error submitting update: ' + err.message);
        } finally {
            sendBtn.disabled = false;
            loading.classList.add('hidden');
        }
    });

    // Ctrl+Enter to send
    textInput.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            form.dispatchEvent(new Event('submit'));
        }
    });

    function addUpdateToFeed(text, data, screenshotCount) {
        const parsed = data.parsed || {};
        const teamUpdates = parsed.team_updates || [];
        const actionItems = parsed.action_items || [];
        const blockers = parsed.blockers || [];

        let tagsHtml = '';
        for (const tu of teamUpdates) {
            tagsHtml += `
                <span class="text-xs font-semibold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">${tu.team_member_name}</span>
                <span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">${tu.project_name}</span>
                <span class="text-xs px-2 py-0.5 rounded ${
                    tu.status === 'completed' ? 'bg-green-50 text-green-700' :
                    tu.status === 'blocked' ? 'bg-red-50 text-red-700' :
                    'bg-blue-50 text-blue-700'
                }">${tu.status}</span>
            `;
        }

        let parsedHtml = '';
        for (const tu of teamUpdates) {
            parsedHtml += `<p class="text-sm text-gray-700 ml-2 mb-2">${tu.summary}</p>`;
        }
        for (const ai of actionItems) {
            parsedHtml += `<p class="text-sm text-amber-700">Action: ${ai.description}</p>`;
        }
        for (const b of blockers) {
            parsedHtml += `<p class="text-sm text-red-700">Blocker: ${b.description}</p>`;
        }
        if (parsed.general_notes) {
            parsedHtml += `<p class="text-sm text-gray-500 italic">${parsed.general_notes}</p>`;
        }

        const html = `
        <div class="fade-in">
            <div class="flex justify-end mb-2">
                <div class="chat-bubble bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-2 shadow">
                    <p>${text}</p>
                    ${screenshotCount > 0 ? `<p class="text-indigo-200 text-xs mt-1">+ ${screenshotCount} screenshot(s)</p>` : ''}
                    <p class="text-indigo-200 text-xs mt-1">via web</p>
                </div>
            </div>
            <div class="flex justify-start mb-2">
                <div class="chat-bubble bg-white border rounded-2xl rounded-bl-md px-4 py-2 shadow-sm">
                    <div class="flex flex-wrap items-center gap-2 mb-1">${tagsHtml}</div>
                    ${parsedHtml}
                </div>
            </div>
        </div>`;

        feed.insertAdjacentHTML('afterbegin', html);
        feed.scrollTop = 0;
    }

    // Scroll feed to top (newest first)
    feed.scrollTop = 0;
});
