// VocalPay Dashboard JavaScript

// Application State
const AppState = {
    token: localStorage.getItem('access_token'),
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    mediaRecorder: null,
    audioChunks: [],
    recordingStartTime: null,
    timerInterval: null
};

// Check authentication on load
if (!AppState.token || !AppState.user) {
    window.location.href = '/signin';
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    displayUserInfo();
    loadTransactions();
});

function displayUserInfo() {
    if (AppState.user) {
        document.getElementById('userGreeting').textContent = 
            `Welcome, ${AppState.user.full_name || AppState.user.email}`;
        
        if (AppState.user.user_id) {
            const shortId = AppState.user.user_id.substring(0, 8);
            document.getElementById('accountId').textContent = `****${shortId}`;
        }
    }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = '/signin';
}

function scrollToHistory() {
    document.getElementById('historySection').scrollIntoView({ behavior: 'smooth' });
}

function openVoiceModal() {
    document.getElementById('voiceModal').classList.remove('hidden');
    document.getElementById('voiceModal').classList.add('flex');
    resetVoiceModal();
}

function closeVoiceModal() {
    if (AppState.mediaRecorder && AppState.mediaRecorder.state === 'recording') {
        AppState.mediaRecorder.stop();
    }
    document.getElementById('voiceModal').classList.add('hidden');
    document.getElementById('voiceModal').classList.remove('flex');
    resetVoiceModal();
}

function resetVoiceModal() {
    document.getElementById('recordingTimer').classList.add('hidden');
    document.getElementById('startRecordBtn').classList.remove('hidden');
    document.getElementById('stopRecordBtn').classList.add('hidden');
    document.getElementById('processingIndicator').classList.add('hidden');
    document.getElementById('voiceStatus').textContent = 'Example: "Transfer 500 rupees to Rohan"';
    AppState.audioChunks = [];
    if (AppState.timerInterval) {
        clearInterval(AppState.timerInterval);
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        AppState.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });

        AppState.audioChunks = [];
        
        AppState.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                AppState.audioChunks.push(event.data);
            }
        };

        AppState.mediaRecorder.onstop = () => {
            stream.getTracks().forEach(track => track.stop());
            processVoiceCommand();
        };

        AppState.mediaRecorder.start();
        AppState.recordingStartTime = Date.now();

        document.getElementById('startRecordBtn').classList.add('hidden');
        document.getElementById('stopRecordBtn').classList.remove('hidden');
        document.getElementById('recordingTimer').classList.remove('hidden');
        document.getElementById('voiceStatus').textContent = '🔴 Recording... Speak your payment command now';

        AppState.timerInterval = setInterval(updateTimer, 100);

        setTimeout(() => {
            if (AppState.mediaRecorder && AppState.mediaRecorder.state === 'recording') {
                stopRecording();
            }
        }, 10000);

    } catch (error) {
        console.error('Microphone access error:', error);
        document.getElementById('voiceStatus').innerHTML = 
            '<span class="text-red-400">❌ Microphone access denied. Please enable microphone permissions.</span>';
    }
}

function updateTimer() {
    if (!AppState.recordingStartTime) return;
    
    const elapsed = Date.now() - AppState.recordingStartTime;
    const seconds = Math.floor(elapsed / 1000);
    const milliseconds = Math.floor((elapsed % 1000) / 100);
    
    const display = `${String(seconds).padStart(2, '0')}:${milliseconds}`;
    document.getElementById('timerDisplay').textContent = display;
}

function stopRecording() {
    if (AppState.mediaRecorder && AppState.mediaRecorder.state === 'recording') {
        AppState.mediaRecorder.stop();
        if (AppState.timerInterval) {
            clearInterval(AppState.timerInterval);
        }
        
        document.getElementById('stopRecordBtn').classList.add('hidden');
        document.getElementById('recordingTimer').classList.add('hidden');
        document.getElementById('processingIndicator').classList.remove('hidden');
        document.getElementById('voiceStatus').textContent = 'Processing your voice command...';
    }
}


async function processVoiceCommand() {
    try {
        const audioBlob = new Blob(AppState.audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'voice_command.webm');

        const response = await fetch('/api/v1/transactions/initiate', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${AppState.token}` },
            body: formData
        });

        const data = await response.json();
        closeVoiceModal();

        if (response.ok && data.success) {
            showXaiAlert('success', 'Transaction Approved', data.rationale, {
                'Risk': data.risk_tier, 'TX ID': data.transaction_id
            });
        } else if (response.status === 403) {
            showXaiAlert('warning', 'Verification Required', data.detail?.rationale, {
                'Risk': data.detail?.risk_tier, 'TX ID': data.detail?.transaction_id
            });
        } else if (response.status === 401) {
            showXaiAlert('error', 'Transaction Blocked', 'Security alert', { 'Risk': 'CRITICAL' });
        } else {
            showXaiAlert('error', 'Transaction Failed', data.detail, {});
        }

        setTimeout(() => loadTransactions(), 1000);
    } catch (error) {
        closeVoiceModal();
        showXaiAlert('error', 'Network Error', 'Unable to connect to server', {});
    }
}

function showXaiAlert(type, title, rationale, metrics) {
    const styles = {
        success: { border: 'border-emerald-500', iconBg: 'bg-emerald-500/20', iconColor: 'text-emerald-400', icon: 'fa-check-circle' },
        warning: { border: 'border-amber-500', iconBg: 'bg-amber-500/20', iconColor: 'text-amber-400', icon: 'fa-exclamation-triangle' },
        error: { border: 'border-red-500', iconBg: 'bg-red-500/20', iconColor: 'text-red-400', icon: 'fa-times-circle' }
    };
    const style = styles[type];
    
    document.getElementById('xaiAlert').className = `glassmorphism rounded-2xl p-6 mb-6 border-l-4 fade-in ${style.border}`;
    document.getElementById('xaiIcon').innerHTML = `<i class="fas ${style.icon} text-2xl ${style.iconColor}"></i>`;
    document.getElementById('xaiTitle').textContent = title;
    document.getElementById('xaiRationale').textContent = rationale;
    
    let metricsHtml = '';
    for (const [key, value] of Object.entries(metrics)) {
        if (value) {
            metricsHtml += `<div class="bg-white/5 rounded-lg p-3"><p class="text-slate-400 text-xs">${key}</p><p class="text-white text-sm font-semibold">${value}</p></div>`;
        }
    }
    document.getElementById('xaiMetrics').innerHTML = metricsHtml;
    document.getElementById('xaiAlert').classList.remove('hidden');
}

function closeXaiAlert() {
    document.getElementById('xaiAlert').classList.add('hidden');
}

async function loadTransactions() {
    const tbody = document.getElementById('transactionList');
    const mocks = [
        { date: '2026-08-12 10:30 AM', recipient: 'Rohan Kumar', amount: 500, risk_level: 'LOW', status: 'COMPLETED' },
        { date: '2026-08-11 03:15 PM', recipient: 'Priya Sharma', amount: 1250, risk_level: 'MEDIUM', status: 'VERIFIED' }
    ];
    
    const riskColors = { LOW: 'bg-emerald-500/20 text-emerald-400', MEDIUM: 'bg-amber-500/20 text-amber-400', HIGH: 'bg-red-500/20 text-red-400' };
    const statusColors = { COMPLETED: 'text-emerald-400', VERIFIED: 'text-blue-400' };
    
    tbody.innerHTML = mocks.map(tx => `
        <tr class="border-b border-white/5 hover:bg-white/5">
            <td class="py-4 text-slate-300 text-sm">${tx.date}</td>
            <td class="py-4 text-white font-medium">${tx.recipient}</td>
            <td class="py-4 text-white font-semibold">₹${tx.amount.toFixed(2)}</td>
            <td class="py-4"><span class="px-2 py-1 ${riskColors[tx.risk_level]} rounded-full text-xs">${tx.risk_level}</span></td>
            <td class="py-4 ${statusColors[tx.status]} font-medium"><i class="fas fa-check-circle mr-1"></i>${tx.status}</td>
        </tr>
    `).join('');
}
