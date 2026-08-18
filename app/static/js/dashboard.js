// VocalPay Dashboard JavaScript

// Application State (no more localStorage!)
const AppState = {
    user: null,  // Will be fetched from /me endpoint
    mediaRecorder: null,
    audioChunks: [],
    recordingStartTime: null,
    timerInterval: null
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async () => {
    await fetchCurrentUser();  // Check auth via cookie
    displayUserInfo();
    loadTransactions();
});

// Fetch current user from backend (validates cookie)
async function fetchCurrentUser() {
    try {
        const response = await fetch('/api/v1/auth/me', {
            credentials: 'include'  // Send cookies
        });
        
        if (!response.ok) {
            // Not authenticated, redirect to signin
            window.location.href = '/signin';
            return;
        }
        
        AppState.user = await response.json();
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/signin';
    }
}

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

async function logout() {
    try {
        // Call logout endpoint to clear cookie
        await fetch('/api/v1/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });
    } catch (error) {
        console.error('Logout failed:', error);
    }
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
            credentials: 'include',  // Send httpOnly cookie
            body: formData
        });

        const data = await response.json();
        closeVoiceModal();

        if (response.ok && data.success) {
            showXaiAlert('success', 'Transaction Approved', data.rationale, {
                'Risk': data.risk_tier, 'TX ID': data.transaction_id
            });
        } else if (response.status === 403) {
            // Step-up verification required
            const detail = data.detail || {};
            showVerificationModal(detail);
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

async function loadTransactions(limit = 20, offset = 0) {
    const tbody = document.getElementById('transactionList');
    
    try {
        // Fetch real transactions from backend API
        const response = await fetch(`/api/v1/transactions/history?limit=${limit}&offset=${offset}`, {
            method: 'GET',
            credentials: 'include'  // Send httpOnly cookie
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                // Token expired, redirect to login
                window.location.href = '/signin';
                return;
            }
            throw new Error('Failed to load transaction history');
        }
        
        const data = await response.json();
        const transactions = data.transactions || [];
        
        // Check if no transactions exist
        if (transactions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-8 text-center text-slate-400">
                        <i class="fas fa-inbox text-4xl mb-3 block"></i>
                        <p class="text-lg">No transactions yet</p>
                        <p class="text-sm mt-2">Try making a voice transfer to see it here!</p>
                    </td>
                </tr>`;
            return;
        }
        
        // Color schemes for status and risk
        const riskColors = { 
            LOW: 'bg-emerald-500/20 text-emerald-400', 
            MEDIUM: 'bg-amber-500/20 text-amber-400', 
            HIGH: 'bg-red-500/20 text-red-400',
            CRITICAL: 'bg-red-600/20 text-red-500'
        };
        const statusColors = { 
            COMPLETED: 'text-emerald-400', 
            VERIFIED: 'text-blue-400',
            SUCCESS: 'text-emerald-400',
            PENDING: 'text-amber-400',
            FAILED: 'text-red-400'
        };
        
        // Render transactions dynamically
        tbody.innerHTML = transactions.map(tx => {
            // Format date
            const date = tx.created_at ? new Date(tx.created_at).toLocaleString('en-IN', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            }) : 'Unknown';
            
            // Transaction ID or system-generated
            const recipient = tx.transaction_id ? tx.transaction_id.substring(0, 8) : 'Unknown';
            
            // Format amount
            const amount = typeof tx.amount === 'number' ? tx.amount.toFixed(2) : '0.00';
            
            // Risk level with fallback
            const riskLevel = tx.risk_level || 'UNKNOWN';
            const riskColorClass = riskColors[riskLevel] || 'bg-slate-500/20 text-slate-400';
            
            // Status with fallback
            const status = tx.status || 'UNKNOWN';
            const statusColorClass = statusColors[status] || 'text-slate-400';
            const statusIcon = tx.success ? 'fa-check-circle' : 'fa-times-circle';
            
            return `
                <tr class="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer" 
                    onclick="showTransactionDetails('${tx.transaction_id}')"
                    title="Click to view details">
                    <td class="py-4 text-slate-300 text-sm">${date}</td>
                    <td class="py-4 text-white font-medium">ID: ${recipient}</td>
                    <td class="py-4 text-white font-semibold">₹${amount}</td>
                    <td class="py-4">
                        <span class="px-2 py-1 ${riskColorClass} rounded-full text-xs font-medium">
                            ${riskLevel}
                        </span>
                    </td>
                    <td class="py-4 ${statusColorClass} font-medium">
                        <i class="fas ${statusIcon} mr-1"></i>${status}
                    </td>
                </tr>`;
        }).join('');
        
        console.log(`✅ Loaded ${transactions.length} transactions (limit: ${limit}, offset: ${offset})`);
        
    } catch (error) {
        console.error('❌ Failed to load transactions:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="py-8 text-center text-red-400">
                    <i class="fas fa-exclamation-triangle text-4xl mb-3 block"></i>
                    <p class="text-lg">Failed to load transactions</p>
                    <p class="text-sm mt-2">${error.message}</p>
                </td>
            </tr>`;
    }
}

function showTransactionDetails(transactionId) {
    // Placeholder function for future transaction detail modal
    console.log('Transaction details:', transactionId);
    alert(`Transaction ID: ${transactionId}\n\nDetailed view coming soon!`);
}


// Verification functions placeholder

let currentVerification={transactionId:null,riskTier:null,challengePhrase:null,otpCode:null,expiresAt:null};
let challengeMediaRecorder=null,challengeAudioChunks=[],challengeRecordingTimer=null,challengeSeconds=0;

function showVerificationModal(data){currentVerification={transactionId:data.transaction_id,riskTier:data.risk_tier,challengePhrase:data.challenge_phrase||null,expiresAt:data.expires_at};const modal=document.getElementById('verifyModal'),otpCard=document.getElementById('otpCard'),challengeCard=document.getElementById('challengeCard'),description=document.getElementById('verifyDescription');otpCard.classList.add('hidden');challengeCard.classList.add('hidden');if(data.risk_tier==='MEDIUM'){description.textContent=data.otp_sent_to_email?'Enter the 6-digit code sent to your registered email':'Enter your 6-digit verification code';otpCard.classList.remove('hidden');document.getElementById('otpDisplay').textContent='Check your registered email for the verification code.';const otpInput=document.getElementById('otpInput');otpInput.value='';setTimeout(()=>otpInput.focus(),300)}else if(data.risk_tier==='HIGH'){description.textContent='Speak the phrase';challengeCard.classList.remove('hidden');document.getElementById('challengePhrase').textContent=data.challenge_phrase}startExpiryCountdown(data.expires_at);modal.classList.remove('hidden');modal.classList.add('flex')}

function closeVerifyModal(){document.getElementById('verifyModal').classList.add('hidden');if(challengeMediaRecorder&&challengeMediaRecorder.state==='recording')challengeMediaRecorder.stop();clearInterval(challengeRecordingTimer)}

async function submitOTP(){const otpInput=document.getElementById('otpInput').value.trim();if(!otpInput||otpInput.length!==6){showXaiAlert('error','Invalid','Enter 6 digits',{});return}const formData=new FormData();formData.append('transaction_id',currentVerification.transactionId);formData.append('otp_code',otpInput);const response=await fetch('/api/v1/transactions/verify',{method:'POST',credentials:'include',body:formData});const result=await response.json();if(response.ok&&result.success){closeVerifyModal();showXaiAlert('success','Verified','Approved!',{});await loadTransactions()}else{showXaiAlert('error','Failed','Invalid code',{})}}

async function startChallengeRecording(){const stream=await navigator.mediaDevices.getUserMedia({audio:true});challengeAudioChunks=[];challengeMediaRecorder=new MediaRecorder(stream);challengeMediaRecorder.ondataavailable=e=>{if(e.data.size>0)challengeAudioChunks.push(e.data)};challengeMediaRecorder.onstop=async()=>{const audioBlob=new Blob(challengeAudioChunks,{type:'audio/webm'});await submitChallengeAudio(audioBlob);stream.getTracks().forEach(t=>t.stop())};challengeMediaRecorder.start();document.getElementById('startChallengeBtn').classList.add('hidden');document.getElementById('stopChallengeBtn').classList.remove('hidden');document.getElementById('challengeRecordingTimer').classList.remove('hidden');challengeSeconds=0;challengeRecordingTimer=setInterval(()=>{challengeSeconds++;document.getElementById('challengeTimerDisplay').textContent=`${String(Math.floor(challengeSeconds/60)).padStart(2,'0')}:${String(challengeSeconds%60).padStart(2,'0')}`;if(challengeSeconds>=10)stopChallengeRecording()},1000)}

function stopChallengeRecording(){if(challengeMediaRecorder&&challengeMediaRecorder.state==='recording')challengeMediaRecorder.stop();clearInterval(challengeRecordingTimer);document.getElementById('startChallengeBtn').classList.remove('hidden');document.getElementById('stopChallengeBtn').classList.add('hidden');document.getElementById('challengeRecordingTimer').classList.add('hidden')}

async function submitChallengeAudio(audioBlob){const formData=new FormData();formData.append('transaction_id',currentVerification.transactionId);formData.append('audio_file',audioBlob,'challenge.webm');showXaiAlert('warning','Processing','Verifying...',{});const response=await fetch('/api/v1/transactions/verify',{method:'POST',credentials:'include',body:formData});const result=await response.json();if(response.ok&&result.success){closeVerifyModal();showXaiAlert('success','Verified','Voice passed!',{});await loadTransactions()}else{showXaiAlert('error','Failed','Voice did not match',{})}}

function startExpiryCountdown(expiresAt){const expiryTime=new Date(expiresAt);const update=()=>{const remaining=Math.max(0,expiryTime-new Date());if(remaining===0){closeVerifyModal();showXaiAlert('error','Expired','Window closed',{});return}const mins=Math.floor(remaining/60000),secs=Math.floor((remaining%60000)/1000);document.getElementById('verifyExpiry').textContent=`${mins}:${String(secs).padStart(2,'0')}`};update();setInterval(update,1000)}
