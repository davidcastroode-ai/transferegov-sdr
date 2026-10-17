
// ===================== cartões clicáveis: clicar num cartão mostra a lista do que ele soma =====================
// a página preenche KPI_DEF[chave] = {tit, lista, cols} a cada render e marca o cartão com data-kpi="chave"
var KPI_DEF = window.KPI_DEF || {}; window.KPI_DEF = KPI_DEF;
function kpiDepois(){
  document.querySelectorAll('[data-kpi]').forEach(c => { c.classList.add('kpi-cl'); c.classList.toggle('kpi-on', c.dataset.kpi === window.__kpi); });
  let box = document.getElementById('kpLista');
  if(!box){ const ref = document.querySelector('[data-kpi]'); if(!ref) return; const grade = ref.closest('.kp') || ref.parentElement;
    box = document.createElement('div'); box.id = 'kpLista'; grade.parentNode.insertBefore(box, grade.nextSibling); }
  // a caixa fica logo abaixo da fileira do cartão clicado
  const on = window.__kpi && document.querySelector(`[data-kpi="${window.__kpi}"]`);
  if(on){ const grade = on.closest('.kp') || on.parentElement; if(grade.nextSibling !== box) grade.parentNode.insertBefore(box, grade.nextSibling); }
  const d = window.__kpi && (window.KPI_DEF||{})[window.__kpi];
  if(!d){ box.innerHTML = ''; return; }
  box.innerHTML = `<section class="card kpi-box"><div class="kpi-cab"><div><h3>📋 ${esc(d.tit)}</h3><p class="d">${d.lista.length.toLocaleString('pt-BR')} registro(s) · clique na linha para abrir a ficha</p></div>
    <div><button type="button" class="kpi-bt" data-kpicsv="1">⬇ Baixar lista (CSV)</button><button type="button" class="kpi-bt" data-kpifecha="1">✕ Fechar</button></div></div>
    ${tabela('k', d.lista, d.cols, 10)}</section>`;
}
(function(){
  const css = document.createElement('style');
  css.textContent = `.kpi-cl{cursor:pointer;transition:transform .12s, box-shadow .12s}.kpi-cl:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(20,40,60,.16)}
  .kpi-on{outline:3px solid #2fae5c;outline-offset:-3px}.kpi-box{border:2px solid #2fae5c}.kpi-cab{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}
  .kpi-bt{border:1px solid #b9c7d3;background:#fff;color:#1f4e79;font:600 12.5px inherit;font-family:inherit;padding:6px 12px;border-radius:8px;cursor:pointer;margin-left:6px}`;
  document.head.appendChild(css);
  const _render = render;
  render = function(){ _render.apply(this, arguments); try{ kpiDepois(); }catch(e){ console.error(e); } };
  document.addEventListener('click', e => {
    const k = e.target.closest('[data-kpi]');
    if(k){ e.stopImmediatePropagation(); window.__kpi = window.__kpi === k.dataset.kpi ? null : k.dataset.kpi; if(typeof PAG === 'object') PAG.k = 0; kpiDepois();
      const b = document.getElementById('kpLista'); if(b && window.__kpi) b.scrollIntoView({block:'nearest', behavior:'smooth'}); return; }
    if(e.target.closest('[data-kpifecha]')){ e.stopImmediatePropagation(); window.__kpi = null; kpiDepois(); return; }
    if(e.target.closest('[data-kpicsv]')){ e.stopImmediatePropagation(); const d = (window.KPI_DEF||{})[window.__kpi]; if(!d) return;
      const txt = s => String(s ?? '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
      const linhas = [d.cols.map(c => txt(c[0]))].concat(d.lista.map(o => d.cols.map(c => txt(c[1](o)))));
      const csv = '﻿' + linhas.map(l => l.map(v => '"' + v.replace(/"/g, '""') + '"').join(';')).join('\r\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); a.download = (d.tit || 'lista').replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_') + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); return; }
  }, true);
})();
