const m = document.getElementById('app');
const state = { msgs: [] };

function render() {
  m.innerHTML = `
  <div class="bg-gradient-to-br from-blue-50 to-indigo-100 h-full flex flex-col">
    <div class="bg-white shadow-lg border-b border-gray-200 p-4">
      <h1 class="text-2xl font-bold text-gray-800">🗳️ AutoGen Council v2.7.0</h1>
      <p class="text-gray-600">Memory-Powered 5-Head Council with Secure Sandbox Execution</p>
      <div class="mt-2 flex space-x-4 text-sm">
        <span class="px-2 py-1 bg-green-100 text-green-700 rounded">🧠 Memory: 7ms avg</span>
        <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded">🗳️ Council: 5 heads</span>
        <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded">🛡️ Sandbox: 45ms avg</span>
        <span class="px-2 py-1 bg-yellow-100 text-yellow-700 rounded">📊 Success: 87.5%</span>
      </div>
    </div>
    
    <div class="flex-grow overflow-auto p-6" id="messages">
      ${state.msgs.length === 0 ? `
        <div class="text-center text-gray-500 mt-8">
          <div class="text-6xl mb-4">🤖</div>
          <h2 class="text-xl font-semibold mb-2">Welcome to AutoGen Council!</h2>
          <p class="mb-4">Ask me anything - I can help with math, code, logic, and general knowledge.</p>
          <div class="grid grid-cols-2 gap-4 max-w-lg mx-auto text-left">
            <div class="bg-white p-3 rounded shadow cursor-pointer hover:bg-gray-50" onclick="askExample('What is 25 * 16?')">
              <strong>🧮 Math:</strong> What is 25 * 16?
            </div>
            <div class="bg-white p-3 rounded shadow cursor-pointer hover:bg-gray-50" onclick="askExample('Remember my name is Alice')">
              <strong>🧠 Memory:</strong> Remember my name is Alice
            </div>
            <div class="bg-white p-3 rounded shadow cursor-pointer hover:bg-gray-50" onclick="askExample('What is machine learning?')">
              <strong>📚 Knowledge:</strong> What is machine learning?
            </div>
            <div class="bg-white p-3 rounded shadow cursor-pointer hover:bg-gray-50" onclick="askExample('Write a Python hello world')">
              <strong>💻 Code:</strong> Write a Python hello world
            </div>
          </div>
        </div>
      ` : state.msgs.map((msg, i) => `
        <div class="mb-6 max-w-4xl mx-auto">
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div class="flex items-start space-x-3 mb-3">
              <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold text-sm">You</div>
              <div class="flex-1">
                <div class="bg-blue-50 rounded-lg p-3">${msg.q}</div>
              </div>
            </div>
            <div class="flex items-start space-x-3">
              <div class="w-8 h-8 bg-gradient-to-br from-purple-500 to-blue-600 rounded-full flex items-center justify-center text-white text-xs">🤖</div>
              <div class="flex-1">
                <div class="bg-gray-50 rounded-lg p-3">${msg.a}</div>
                
                ${msg.voices && msg.voices.length > 0 ? `
                  <details class="council-panel mt-3 p-2 border border-gray-300 rounded bg-gray-50">
                    <summary class="cursor-pointer font-semibold text-gray-700 hover:text-gray-900">
                      🤖 Council consensus (${msg.voices.length} voices, $${(msg.cost_usd || 0).toFixed(4)})
                    </summary>
                    <div class="mt-2 space-y-2">
                      ${msg.voices.map(v => `
                        <div class="ml-4 p-2 bg-white rounded border">
                          <div class="font-semibold text-sm text-gray-800">${v.voice}</div>
                          <div class="text-xs text-gray-500 mb-1">${v.tokens || 0}t, $${(v.cost || 0).toFixed(4)}, conf: ${Math.round((v.confidence || 0) * 100)}%</div>
                          <div class="text-sm text-gray-700">${v.reply || 'No response'}</div>
                        </div>
                      `).join('')}
                    </div>
                  </details>
                ` : ''}
                
                <div class="mt-2 flex items-center space-x-4 text-xs text-gray-500">
                  <span>⚡ ${msg.ms}ms</span>
                  <span>🎯 ${msg.skill}</span>
                  <span>📊 ${Math.round(msg.confidence * 100)}% confidence</span>
                  <span>🕒 ${new Date(msg.timestamp * 1000).toLocaleTimeString()}</span>
                  ${msg.cost_usd ? `<span>💰 $${msg.cost_usd.toFixed(4)}</span>` : ''}
                </div>
              </div>
            </div>
          </div>
        </div>
      `).join('')}
    </div>
    
    <div class="bg-white border-t border-gray-200 p-4">
      <div class="max-w-4xl mx-auto">
        <div class="flex space-x-3">
          <input id="inp" class="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                 placeholder="Ask me anything... I can help with math, memory, code, and knowledge!" 
                 onkeypress="if(event.key==='Enter') sendMessage()"/>
          <button id="send" class="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white px-6 py-3 rounded-lg font-semibold transition-all duration-200 shadow-md hover:shadow-lg">
            Send
          </button>
        </div>
        <div class="mt-2 flex justify-between items-center text-xs text-gray-500">
          <span>💡 Try: "What is 2+2?", "Remember I like Python", "What is AI?"</span>
          <a href="/admin/" class="text-blue-500 hover:text-blue-700">⚙️ Admin Panel</a>
        </div>
      </div>
    </div>
  </div>`;
  
  // Scroll to bottom
  const messagesDiv = document.getElementById('messages');
  if (messagesDiv) {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }
  
  // Attach event handlers
  document.getElementById('send').onclick = sendMessage;
  document.getElementById('inp').focus();
}

async function sendMessage() {
  const text = document.getElementById('inp').value.trim();
  if (!text) return;
  
  const sendBtn = document.getElementById('send');
  const input = document.getElementById('inp');
  
  // Disable UI during request
  sendBtn.textContent = 'Sending...';
  sendBtn.disabled = true;
  input.disabled = true;
  input.value = '';
  
  try {
    const t0 = performance.now();
    // Use the /hybrid endpoint for Agent-0 + Council routing
    const res = await fetch('/hybrid', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        prompt: text,
        session_id: 'chat_' + Date.now()  // Simple session ID
      })
    });
    
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    
    const payload = await res.json();
    const latency = Math.round(performance.now() - t0);
    
    // Add message to state with Council data
    const msgData = {
      q: text, 
      a: payload.text || 'No response received',
      ms: Math.round(latency),
      skill: payload.model_chain ? payload.model_chain.join(' → ') : 'council',
      confidence: 0.8,  // Default for Council responses
      timestamp: Date.now() / 1000,
      voices: payload.voices || [],  // Council voices
      cost_usd: payload.cost_usd || 0
    };
    
    state.msgs.push(msgData);
    
  } catch (error) {
    console.error('Request failed:', error);
    state.msgs.push({
      q: text,
      a: `❌ Error: ${error.message}. Please check the server connection.`,
      ms: 0,
      skill: 'error',
      confidence: 0,
      timestamp: Date.now() / 1000,
      voices: [],
      cost_usd: 0
    });
  }
  
  // Re-enable UI
  sendBtn.textContent = 'Send';
  sendBtn.disabled = false;
  input.disabled = false;
  input.focus();
  
  render();
}

function askExample(question) {
  document.getElementById('inp').value = question;
  sendMessage();
}

// Initial render
render();

// Add model loading display on page load
document.addEventListener('DOMContentLoaded', function() {
    // Update page title and status with loaded models
    fetch('/models')
        .then(r => r.json())
        .then(m => {
            const modelCount = m.count || 0;
            const providers = m.providers || [];
            const priority = m.priority || [];
            
            // Update page title
            document.title = `AutoGen Council (${modelCount} models)`;
            
            // Update header with provider info
            const headerStats = document.querySelector('.performance-stats');
            if (headerStats) {
                const providerInfo = document.createElement('div');
                providerInfo.className = 'provider-info';
                providerInfo.innerHTML = `
                    🤖 ${modelCount} models | 
                    🔗 ${providers.join(' → ')} | 
                    🎯 Priority: ${priority.join(' → ')}
                `;
                providerInfo.style.cssText = `
                    color: #64748b;
                    font-size: 12px;
                    margin-top: 5px;
                    font-family: 'JetBrains Mono', monospace;
                `;
                headerStats.appendChild(providerInfo);
            }
            
            // Log provider details for debugging
            console.log('🔧 AutoGen Council Provider Status:', {
                models: modelCount,
                providers: providers,
                priority: priority,
                backend: m.backend || 'unknown'
            });
        })
        .catch(e => {
            console.warn('⚠️ Could not load model information:', e);
            document.title = 'AutoGen Council (loading...)';
        });
    
    // ... rest of existing DOMContentLoaded code ...
});
