/**
 * V.E.G.A.S. AIOS Mission Control Application Logic
 * Integrates AI Core renderer, Web Audio SFX synth, Web Speech voice output,
 * WebSocket status streams, 8 Specialist Agents, F1 telemetry, Android Companion status,
 * Goal execution, Agent Inspector modal, and Confirmation gates.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize HTML5 60fps Canvas AI Core Engine
  if (window.AICoreEngine) {
    window.aiCore = new window.AICoreEngine('aiCoreCanvas');
  }

  // UI Elements
  const stateBadge = document.getElementById('coreStateIndicator');
  const systemStateBadge = document.getElementById('systemStateBadge');
  const goalInput = document.getElementById('goalInput');
  const executeBtn = document.getElementById('executeBtn');
  const micWakeBtn = document.getElementById('micWakeBtn');
  const terminalFeed = document.getElementById('terminalFeed');
  const timeline = document.getElementById('executionTimeline');

  // Modals
  const confirmationModal = document.getElementById('confirmationModal');
  const confirmationDetail = document.getElementById('confirmationDetail');
  const confirmApproveBtn = document.getElementById('confirmApproveBtn');
  const confirmCancelBtn = document.getElementById('confirmCancelBtn');

  const agentModal = document.getElementById('agentModal');
  const agentModalTitle = document.getElementById('agentModalTitle');
  const agentModalBody = document.getElementById('agentModalBody');
  const agentModalCloseBtn = document.getElementById('agentModalCloseBtn');

  let activePendingTaskId = null;
  let isListening = false;

  // ------------------------------------------------------------------
  // 1. Telemetry & Status Polling
  // ------------------------------------------------------------------

  async function fetchSystemStatus() {
    if (document.hidden) return;
    try {
      const res = await fetch('/api/system-status');
      if (!res.ok) return;
      const data = await res.json();

      // Header Telemetry
      document.getElementById('telemetryCpu').textContent = data.cpu_percent >= 0 ? `${data.cpu_percent}%` : 'N/A';
      document.getElementById('telemetryRam').textContent = data.mem_used_gb >= 0 ? `${data.mem_used_gb} / ${data.mem_total_gb} GB` : 'N/A';
      
      // F1 Telemetry Gauges
      if (data.cpu_percent >= 0) {
        document.getElementById('gaugeCpuVal').textContent = `${data.cpu_percent}%`;
        document.getElementById('gaugeCpuFill').style.width = `${Math.min(100, data.cpu_percent)}%`;
      }
      if (data.mem_percent >= 0) {
        document.getElementById('gaugeRamVal').textContent = `${data.mem_percent}%`;
        document.getElementById('gaugeRamFill').style.width = `${Math.min(100, data.mem_percent)}%`;
      }

      // Android Companion Telemetry
      if (data.companion) {
        updateCompanionUI(data.companion);
      }

      // Active Plan Timeline
      if (data.planner && data.planner.active_plan) {
        renderPlannerTimeline(data.planner.active_plan);
      }
    } catch (e) {
      // Polling recovers automatically on next interval
    }
  }

  async function fetchAgentsStatus() {
    if (document.hidden) return;
    try {
      const res = await fetch('/api/agents');
      if (!res.ok) return;
      const data = await res.json();
      if (data.agents) {
        data.agents.forEach(agent => {
          const card = document.getElementById(`agent-${agent.role}`);
          if (card) {
            const led = card.querySelector('.agent-status-led');
            if (led) {
              led.style.background = agent.inbox_size > 0 ? 'var(--hud-gold)' : 'var(--hud-green)';
              led.style.boxShadow = agent.inbox_size > 0 ? '0 0 10px var(--hud-gold)' : '0 0 8px var(--hud-green)';
            }
          }
        });
      }
    } catch (e) {
      // Polling recovers automatically on next interval
    }
  }

  function updateCompanionUI(comp) {
    const conn = document.getElementById('compConn');
    const batt = document.getElementById('compBatt');
    const ssid = document.getElementById('compSsid');
    const notifs = document.getElementById('compNotifs');
    const topBatt = document.getElementById('telemetryBattery');
    const topPhone = document.getElementById('telemetryPhone');

    if (comp.connected) {
      conn.textContent = 'Encrypted Wi-Fi Connected';
      conn.style.color = 'var(--hud-green)';
      batt.textContent = `${comp.battery_level || '--'}% (Charging: ${comp.charging})`;
      ssid.textContent = comp.wifi_ssid || 'Home Network';
      notifs.textContent = comp.notifications_count || '0';
      topBatt.textContent = `${comp.battery_level || '--'}%`;
      topPhone.textContent = 'ONLINE';
      topPhone.style.color = 'var(--hud-green)';
    } else {
      conn.textContent = 'Wi-Fi Standby';
      conn.style.color = 'var(--hud-gold)';
      batt.textContent = '--%';
      ssid.textContent = '--';
      notifs.textContent = '0';
      topPhone.textContent = 'STANDBY';
      topPhone.style.color = 'var(--hud-gold)';
    }
  }

  function renderPlannerTimeline(plan) {
    const targetPlan = (plan && plan.plan) ? plan.plan : plan;
    if (!targetPlan || !Array.isArray(targetPlan.steps)) return;
    timeline.innerHTML = '';

    const titleDiv = document.createElement('div');
    titleDiv.style.marginBottom = '6px';
    titleDiv.innerHTML = `<strong style="color:var(--hud-cyan);">Plan ${targetPlan.plan_id}:</strong> ${targetPlan.goal}`;
    timeline.appendChild(titleDiv);

    targetPlan.steps.forEach(step => {
      const stepDiv = document.createElement('div');
      stepDiv.style.padding = '6px';
      stepDiv.style.background = 'rgba(255,255,255,0.03)';
      stepDiv.style.borderRadius = '4px';
      stepDiv.style.marginBottom = '4px';

      let statusColor = 'var(--text-dim)';
      if (step.status === 'success') statusColor = 'var(--hud-green)';
      if (step.status === 'failed') statusColor = 'var(--hud-red)';
      if (step.status === 'blocked') statusColor = 'var(--hud-orange)';

      stepDiv.innerHTML = `
        <div style="display:flex; justify-content:space-between;">
          <span style="color:${statusColor}; font-weight:600;">● Step ${step.step_id} [${step.agent_role}]</span>
          <span>${step.status}</span>
        </div>
        <div style="color:var(--text-main); margin-top:2px;">${step.description}</div>
      `;
      timeline.appendChild(stepDiv);
    });
  }

  function appendLogLine(msg, type = 'info') {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    const ts = new Date().toLocaleTimeString();
    line.textContent = `[${ts}] ${msg}`;
    terminalFeed.appendChild(line);
    terminalFeed.scrollTop = terminalFeed.scrollHeight;
  }

  // ------------------------------------------------------------------
  // 2. Goal Execution & Core State Machine
  // ------------------------------------------------------------------

  async function handleGoalExecute() {
    const goal = goalInput.value.trim();
    if (!goal) return;

    if (window.vegasAudio) window.vegasAudio.playExecuteChime();
    appendLogLine(`Received goal: "${goal}"`, 'info');
    goalInput.value = '';

    // Set AI Core to THINKING state
    if (window.aiCore) window.aiCore.setState('thinking');
    stateBadge.textContent = 'REASONING & PLANNING';
    stateBadge.className = 'core-state-indicator thinking';

    try {
      // Step 1: Create Plan
      const planRes = await fetch('/api/planner/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal })
      });
      const planData = await planRes.json();
      const plan = planData.plan || planData;

      if (planData.error || !plan || !Array.isArray(plan.steps)) {
        appendLogLine(`Planner Error: ${planData?.error || 'Failed to generate execution plan steps.'}`, 'error');
        resetCoreState();
        return;
      }

      appendLogLine(`Plan created (${plan.steps.length} step(s)). Dispatching to agents...`, 'success');
      renderPlannerTimeline(plan);

      // Set AI Core to EXECUTING state
      if (window.aiCore) window.aiCore.setState('executing');
      stateBadge.textContent = 'EXECUTING SUBTASKS';
      stateBadge.className = 'core-state-indicator';

      // Step 2: Execute Plan Steps
      const execRes = await fetch('/api/planner/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_steps: 10 })
      });
      const execData = await execRes.json();

      if (execData.confirmation_required || execData.status === 'needs_confirmation') {
        const confirmText = execData.confirmation_required || execData.last_result?.result || 'Safety gate confirmation required for this action.';
        const taskIdMatch = confirmText.match(/confirm task ([a-f0-9\-]+)/);
        if (taskIdMatch) {
          activePendingTaskId = taskIdMatch[1];
        } else if (execData.task_id) {
          activePendingTaskId = execData.task_id;
        }
        appendLogLine(`Confirmation Required: ${confirmText}`, 'warning');
        showConfirmationModal(confirmText);
      } else {
        const summaryText = execData.status || 'Execution complete.';
        appendLogLine(`Execution result: ${summaryText}`, 'success');
        if (window.vegasAudio) window.vegasAudio.speakText(`Goal completed successfully: ${summaryText}`);
        resetCoreState();
      }

    } catch (err) {
      appendLogLine(`Execution Exception: ${err.message}`, 'error');
      resetCoreState();
    }
  }

  function resetCoreState() {
    if (window.aiCore) window.aiCore.setState('idle');
    stateBadge.textContent = 'AI CORE ONLINE';
    stateBadge.className = 'core-state-indicator';
  }

  function showConfirmationModal(detailText) {
    if (window.vegasAudio) window.vegasAudio.playAlertChime();
    if (window.aiCore) window.aiCore.setState('alert');
    stateBadge.textContent = 'CONFIRMATION REQUIRED';
    stateBadge.className = 'core-state-indicator alert';

    confirmationDetail.textContent = detailText;
    confirmationModal.classList.add('active');
  }

  function hideConfirmationModal() {
    confirmationModal.classList.remove('active');
    resetCoreState();
  }

  // ------------------------------------------------------------------
  // 3. Agent Inspector Modal Handler
  // ------------------------------------------------------------------

  async function openAgentInspector(role) {
    if (window.vegasAudio) window.vegasAudio.playClickChime();
    agentModalTitle.textContent = `${role.toUpperCase()} AGENT INSPECTOR`;
    agentModalBody.textContent = `Fetching tool manifest for ${role}...`;
    agentModal.classList.add('active');

    try {
      const res = await fetch(`/api/agents/${role}`);
      if (!res.ok) {
        agentModalBody.textContent = `Could not fetch detail for agent: ${role}`;
        return;
      }
      const data = await res.json();
      agentModalBody.innerHTML = `
        <div style="margin-bottom:8px;">- Role: <span style="color:var(--hud-cyan);">${data.role}</span></div>
        <div style="margin-bottom:8px;">- Tools Owned: <span style="color:var(--hud-green);">${data.tools ? data.tools.length : 0}</span></div>
        <div style="margin-bottom:8px;">- Inbox Queue: ${data.inbox_size || 0} messages</div>
        <div style="max-height:180px; overflow-y:auto; padding:6px; background:rgba(0,0,0,0.4); border-radius:6px;">
          ${data.tools ? data.tools.map(t => `<div style="margin-bottom:4px;">• <strong>${t.name}</strong>: ${t.description}</div>`).join('') : 'No tools registered'}
        </div>
      `;
    } catch (err) {
      agentModalBody.textContent = `Error inspecting agent: ${err.message}`;
    }
  }

  // ------------------------------------------------------------------
  // 4. Cinematic "Hey Vegas" Voice Trigger
  // ------------------------------------------------------------------

  function toggleVoiceWake() {
    isListening = !isListening;

    if (isListening) {
      if (window.vegasAudio) window.vegasAudio.playWakeChime();
      micWakeBtn.classList.add('active');
      if (window.aiCore) window.aiCore.setState('listening', 0.85);
      stateBadge.textContent = 'LISTENING ("HEY VEGAS")';
      stateBadge.className = 'core-state-indicator listening';
      appendLogLine('Voice engine active — listening for "Hey Vegas" wake phrase...', 'alert');

      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const rec = new SpeechRec();
        rec.continuous = false;
        rec.interimResults = false;
        rec.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          appendLogLine(`Voice captured: "${transcript}"`, 'success');
          goalInput.value = transcript;
          toggleVoiceWake();
          handleGoalExecute();
        };
        rec.onerror = () => toggleVoiceWake();
        rec.start();
      }
    } else {
      micWakeBtn.classList.remove('active');
      resetCoreState();
    }
  }

  // ------------------------------------------------------------------
  // 5. Event Listeners
  // ------------------------------------------------------------------

  executeBtn?.addEventListener('click', handleGoalExecute);
  goalInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleGoalExecute();
  });
  micWakeBtn?.addEventListener('click', toggleVoiceWake);

  confirmApproveBtn?.addEventListener('click', async () => {
    if (window.vegasAudio) window.vegasAudio.playClickChime();
    if (!activePendingTaskId) return;
    const taskId = activePendingTaskId;
    appendLogLine(`Approving task ${taskId}...`, 'info');
    hideConfirmationModal();
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `confirm task ${taskId}` })
      });
      const data = await res.json();
      appendLogLine(`Task ${taskId} result: ${data.response || data.result || 'Executed'}`, 'success');
      if (window.vegasAudio) window.vegasAudio.speakText(`Task approved and executed.`);
    } catch (e) {
      appendLogLine(`Confirmation Error: ${e.message}`, 'error');
    }
    fetchSystemStatus();
  });

  confirmCancelBtn?.addEventListener('click', async () => {
    if (window.vegasAudio) window.vegasAudio.playClickChime();
    if (activePendingTaskId) {
      const taskId = activePendingTaskId;
      try {
        await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: `cancel task ${taskId}` })
        });
      } catch (e) {}
    }
    appendLogLine('Action cancelled by user.', 'alert');
    hideConfirmationModal();
  });

  agentModalCloseBtn?.addEventListener('click', () => {
    if (window.vegasAudio) window.vegasAudio.playClickChime();
    agentModal?.classList.remove('active');
  });

  // Agent Cards Click Event Binding
  document.querySelectorAll('.agent-card').forEach(card => {
    card.addEventListener('click', () => {
      const role = card.getAttribute('data-role');
      if (role) openAgentInspector(role);
    });
  });

  // Initial Data Fetch & Polling Loops
  fetchSystemStatus();
  fetchAgentsStatus();
  setInterval(fetchSystemStatus, 2500);
  setInterval(fetchAgentsStatus, 4000);
});
