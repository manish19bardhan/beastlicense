(function(){
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  async function copyText(text){
    try{ if(navigator.clipboard && window.isSecureContext){ await navigator.clipboard.writeText(text); return true; } }catch(_){}
    const ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly','');
    ta.style.cssText = 'position:fixed;top:-9999px;opacity:0';
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try{ ok = document.execCommand('copy'); }catch(_){}
    document.body.removeChild(ta);
    return ok;
  }

  const status = document.getElementById('copyStatus');
  function announce(msg){ if(!status) return; status.textContent = ''; setTimeout(()=>{ status.textContent = msg; }, 30); }

  document.addEventListener('click', async (e)=>{
    const btn = e.target.closest('[data-copy]');
    if(!btn) return;
    const text = btn.dataset.copy || '';
    if(!text) return;
    const ok = await copyText(text);
    const old = btn.textContent;
    if(ok){
      btn.textContent = 'Copied'; btn.classList.add('copied');
      announce('Copied to clipboard');
      setTimeout(()=>{ btn.textContent = old; btn.classList.remove('copied'); }, 1200);
    } else {
      btn.textContent = 'Failed'; announce('Copy failed');
      setTimeout(()=>{ btn.textContent = old; }, 1200);
    }
  });

  document.querySelectorAll('.alert-dismissible').forEach(el=>{
    setTimeout(()=>{
      if(!el.isConnected) return;
      const inst = window.bootstrap && bootstrap.Alert ? bootstrap.Alert.getOrCreateInstance(el) : null;
      if(inst) inst.close(); else el.remove();
    }, 4500);
  });

  document.querySelectorAll('form').forEach(f=>{
    f.addEventListener('submit', ()=>{
      const btn = f.querySelector('button[type="submit"]');
      if(!btn || btn.disabled) return;
      btn.disabled = true;
      const orig = btn.innerHTML;
      btn.innerHTML = 'Working...';
      setTimeout(()=>{ if(btn.isConnected){ btn.disabled = false; btn.innerHTML = orig; } }, 8000);
    });
  });

  document.querySelectorAll('.license-table').forEach(table => {
    const tbody = table.querySelector('tbody') || table;
    const host = table.closest('.card') || document;
    const sortBtn = host.querySelector('[data-sort-toggle]');
    const customerButtons = table.querySelectorAll('.customer-sort');
    const state = { dir: 1, focusCustomer: null };
    const cellsOf = row => row.querySelector('.customer-cell');

    function render(){
      const rows = Array.from(tbody.querySelectorAll('tr')).filter(r => cellsOf(r));
      rows.sort((a,b)=>{
        const ac = cellsOf(a)?.dataset.customer || '';
        const bc = cellsOf(b)?.dataset.customer || '';
        const ai = parseInt(cellsOf(a)?.dataset.licenseId || '0', 10);
        const bi = parseInt(cellsOf(b)?.dataset.licenseId || '0', 10);
        if(state.focusCustomer){
          const ar = ac === state.focusCustomer ? 0 : 1;
          const br = bc === state.focusCustomer ? 0 : 1;
          if(ar !== br) return ar - br;
        }
        return state.dir * (ac.localeCompare(bc) || (ai - bi));
      });
      rows.forEach(r => tbody.appendChild(r));
      if(sortBtn){
        sortBtn.textContent = state.focusCustomer
          ? 'Clear selection'
          : (state.dir === 1 ? 'Arrange: Customer A\u2192Z' : 'Arrange: Customer Z\u2192A');
      }
    }

    sortBtn?.addEventListener('click', ()=>{
      if(state.focusCustomer) state.focusCustomer = null; else state.dir *= -1;
      customerButtons.forEach(x => x.classList.remove('selected'));
      render();
    });

    customerButtons.forEach(btn => btn.addEventListener('click', ()=>{
      const c = btn.dataset.customer;
      state.focusCustomer = (state.focusCustomer === c) ? null : c;
      customerButtons.forEach(x => x.classList.remove('selected'));
      if(state.focusCustomer) btn.classList.add('selected');
      render();
    }));
  });

  if(!reduceMotion && window.matchMedia('(hover:hover)').matches){
    document.querySelectorAll('.card').forEach(card=>{
      card.addEventListener('pointermove', e=>{
        const r = card.getBoundingClientRect();
        card.style.setProperty('--mx', ((e.clientX - r.left) / r.width) * 100 + '%');
        card.style.setProperty('--my', ((e.clientY - r.top) / r.height) * 100 + '%');
      }, {passive:true});
    });
  }

  function animateNumber(el){
    const raw = (el.textContent || '').trim();
    const target = parseFloat(raw.replace(/[^\d.-]/g, ''));
    if(!isFinite(target) || target === 0) return;
    const isDecimal = raw.includes('.');
    const start = performance.now();
    const dur = 850;
    el.textContent = isDecimal ? '0.00' : '0';
    function tick(now){
      const t = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = target * eased;
      el.textContent = isDecimal ? v.toFixed(2) : Math.round(v).toLocaleString();
      if(t < 1) requestAnimationFrame(tick);
      else el.textContent = isDecimal ? target.toFixed(2) : target.toLocaleString();
    }
    requestAnimationFrame(tick);
  }

  const countables = document.querySelectorAll('.stat-card .stat-value, .stat-mini');
  if(countables.length && !reduceMotion){
    if('IntersectionObserver' in window){
      const io = new IntersectionObserver(entries=>{
        entries.forEach(en=>{ if(en.isIntersecting){ animateNumber(en.target); io.unobserve(en.target); } });
      }, {threshold:.4});
      countables.forEach(el => io.observe(el));
    }else{
      countables.forEach(animateNumber);
    }
  }
})();