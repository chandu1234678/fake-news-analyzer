/* pricing.js — Razorpay payment flow for PiNE AI */

const API = window.API_BASE || 'https://fake-news-analyzer-j6ka.onrender.com';

const PLANS = {
  starter:    { name: 'Starter',    price: 99,   label: '₹99/month' },
  pro:        { name: 'Pro',        price: 499,  label: '₹499/month' },
  enterprise: { name: 'Enterprise', price: 2999, label: '₹2,999/month' },
};

let selectedPlan = null;

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('back-btn').addEventListener('click', () => history.back());

  // Load current user tier
  try {
    const token = await getToken();
    if (token) {
      const res = await fetch(`${API}/quota/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        updateCurrentPlan(data.tier, data.used, data.limit);
      }
    }
  } catch (e) { /* silent */ }

  // Attach plan button listeners
  document.querySelectorAll('.plan-card[data-plan]').forEach(card => {
    const btn = card.querySelector('.plan-btn');
    btn.addEventListener('click', () => openPaymentModal(card.dataset.plan));
  });

  // Modal buttons
  document.getElementById('confirm-payment-btn').addEventListener('click', initiatePayment);
  document.getElementById('cancel-payment-btn').addEventListener('click', closePaymentModal);
  document.getElementById('payment-modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closePaymentModal();
  });
});

function updateCurrentPlan(tier, used, limit) {
  const nameEl = document.getElementById('current-plan-name');
  const quotaEl = document.getElementById('current-plan-quota');
  const tierMap = {
    free:       'Free',
    starter:    'Starter',
    pro:        'Pro',
    enterprise: 'Enterprise',
    anonymous:  'Free',
  };
  nameEl.textContent = tierMap[tier] || 'Free';
  const limitStr = limit === -1 ? 'Unlimited' : limit;
  quotaEl.textContent = `${used} / ${limitStr} checks this month`;

  // Mark current plan card
  document.querySelectorAll('.plan-card').forEach(c => c.classList.remove('current'));
  const currentCard = document.getElementById(`plan-${tier}`);
  if (currentCard) {
    currentCard.classList.add('current');
    const btn = currentCard.querySelector('.plan-btn');
    btn.textContent = 'Current Plan';
    btn.className = 'plan-btn plan-btn-current';
    btn.disabled = true;
  }
}

function openPaymentModal(plan) {
  selectedPlan = plan;
  const info = PLANS[plan];
  document.getElementById('modal-title').textContent = `Upgrade to ${info.name}`;
  document.getElementById('modal-sub').textContent = `You're upgrading to the ${info.name} plan`;
  document.getElementById('summary-plan').textContent = info.name;
  document.getElementById('summary-total').textContent = info.label;
  document.getElementById('payment-modal-overlay').style.display = 'flex';
}

function closePaymentModal() {
  document.getElementById('payment-modal-overlay').style.display = 'none';
  selectedPlan = null;
}

async function initiatePayment() {
  if (!selectedPlan) return;
  const btn = document.getElementById('confirm-payment-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="material-symbols-outlined ms-16">hourglass_empty</span> Creating order…';

  try {
    const token = await getToken();
    if (!token) {
      showToast('Please sign in to upgrade', 'error');
      closePaymentModal();
      chrome.tabs && chrome.tabs.create ? null : (window.location.href = 'login.html');
      return;
    }

    const res = await fetch(`${API}/payment/create-order`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ plan: selectedPlan }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create order');
    }

    const order = await res.json();

    // Open Razorpay checkout in a new tab (Chrome extensions can't load external scripts inline)
    const checkoutUrl = `${API}/payment/checkout?order_id=${order.order_id}&plan=${selectedPlan}&amount=${order.amount}&key=${order.key_id}`;
    chrome.tabs.create({ url: checkoutUrl });
    closePaymentModal();
    showToast('Opening payment page…', 'success');

  } catch (err) {
    showToast(err.message || 'Payment failed', 'error');
    btn.disabled = false;
    btn.innerHTML = '<span class="material-symbols-outlined ms-16">credit_card</span> Proceed to Payment';
  }
}

async function getToken() {
  return new Promise(resolve => {
    chrome.storage.local.get(['token'], r => resolve(r.token || null));
  });
}

function showToast(msg, type = '') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}
