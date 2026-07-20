const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){
 const [p,d]=await Promise.all([fetch('/api/policies').then(r=>r.json()),fetch('/api/policy-decisions?limit=50').then(r=>r.json())]);
 document.querySelector('#policies').innerHTML=(p.policies||[]).map(x=>`<article><h3>${esc(x.name)}</h3><p><strong>${esc(x.decision)}</strong> · ${esc(x.operation_class)}</p><small>${esc(x.policy_id)}</small></article>`).join('')||'<p>No policies found.</p>';
 document.querySelector('#decisions').innerHTML=`<table><thead><tr><th>Time</th><th>Operation</th><th>Decision</th><th>User</th><th>Reason</th></tr></thead><tbody>${(d.decisions||[]).map(x=>`<tr><td>${esc(x.created_at)}</td><td>${esc(x.operation)}</td><td>${esc(x.decision)}</td><td>${esc(x.requested_by)}</td><td>${esc(x.reason)}</td></tr>`).join('')}</tbody></table>`;
}
load().catch(e=>document.body.insertAdjacentHTML('beforeend',`<pre>${esc(e)}</pre>`));
