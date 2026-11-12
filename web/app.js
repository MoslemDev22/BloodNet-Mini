const API = (window.BLOODNET_API || 'http://127.0.0.1:8000').replace(/\/$/, '');
const TOKENS = { hospital: 'hospital-token', coordinator: 'coordinator-token', donor: 'donor-demo-token' };
const $ = (id) => document.getElementById(id);
const state = { requests: [], inventory: [], hospitals: [], donorId: '', donorToken: TOKENS.donor, reviewRequestId: '' };
const fa = { product: {red_cells:'گلبول قرمز',platelets:'پلاکت',plasma:'پلاسما'}, urgency:{critical:'بحرانی',urgent:'فوری',planned:'برنامه‌ریزی‌شده'}, status:{open:'باز',mobilizing:'در حال فراخوان',partially_fulfilled:'تأمین ناقص',fulfilled:'تأمین کامل',cancelled:'لغوشده',expired:'منقضی',pending_review:'در انتظار تأیید'}, donor:{notified:'دعوت‌شده',accepted:'پذیرفته',declined:'ردشده',en_route:'در مسیر',arrived:'رسیده',screen_pass:'غربالگری موفق',screen_fail:'غربالگری ناموفق',donated:'اهدا انجام شد',no_show:'عدم مراجعه',stopped:'متوقف‌شده'} };
async function api(path, options={}) {
  const headers = {'Content-Type':'application/json', ...(options.headers||{})};
  const res = await fetch(API + path, {...options, headers});
  let data={}; try { data=await res.json(); } catch {}
  if (!res.ok) throw new Error(data?.error?.message || data?.error?.code || `HTTP ${res.status}`);
  return data;
}
function toast(message){const el=$('toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),2800)}
function showMessage(id,msg,type){const el=$(id);el.textContent=msg;el.className=`message ${type}`;el.classList.remove('hidden')}
function safe(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function statusBadge(s){return `<span class="status ${safe(s)}">${safe(fa.status[s]||s)}</span>`}
function productLabel(s){return fa.product[s]||s}
function renderTable(rows, target, detailed=false){
  if(!rows.length){$(target).innerHTML='<div class="empty-state">هنوز درخواستی ثبت نشده است.</div>';return}
  $(target).innerHTML=`<table><thead><tr><th>شناسه</th><th>بیمارستان</th><th>فرآورده</th><th>گروه</th><th>درخواستی</th><th>تأمین‌شده</th><th>موجودی در راه</th><th>فوریت</th><th>وضعیت</th><th></th></tr></thead><tbody>${rows.map(r=>`<tr><td><b dir="ltr">${safe(r.request_id)}</b></td><td>${safe(hospitalName(r.hospital_id))}</td><td>${safe(productLabel(r.product))}</td><td><span class="blood">${safe(r.blood_group)}</span></td><td>${r.needed}</td><td>${r.fulfilled}</td><td>${r.stock_inflight||0}</td><td>${safe(fa.urgency[r.urgency]||r.urgency)}</td><td>${statusBadge(r.status)}</td><td><button class="link-btn" data-detail="${safe(r.request_id)}">جزئیات</button></td></tr>`).join('')}</tbody></table>`;
  $(target).querySelectorAll('[data-detail]').forEach(b=>b.addEventListener('click',()=>loadDetail(b.dataset.detail)));
}
function hospitalName(id){return state.hospitals.find(x=>x.hospital_id===id)?.name||id}
async function loadMeta(){const d=await api('/meta');state.hospitals=d.hospitals||[];$('hospitalId').innerHTML=state.hospitals.map(h=>`<option value="${safe(h.hospital_id)}">${safe(h.name)} (${safe(h.hospital_id)})</option>`).join('')}
async function loadRequests(){const d=await api('/requests',{headers:{Authorization:`Bearer ${TOKENS.hospital}`}});state.requests=d.items||[];renderTable(state.requests.slice(0,7),'overviewRequests');renderTable(state.requests,'requestsTable');$('statTotal').textContent=state.requests.length;$('statOpen').textContent=state.requests.filter(r=>['open','mobilizing','partially_fulfilled','pending_review'].includes(r.status)).length;$('statDone').textContent=state.requests.filter(r=>r.status==='fulfilled').length}
async function loadInventory(){const d=await api('/inventory',{headers:{Authorization:`Bearer ${TOKENS.coordinator}`}});state.inventory=d.items||[];const total=state.inventory.reduce((a,x)=>a+Number(x.units||0),0);$('statStock').textContent=total.toLocaleString('fa-IR');renderInventory()}
function renderInventory(){const q=$('inventorySearch').value.trim().toLowerCase(),p=$('inventoryProduct').value;const rows=state.inventory.filter(x=>(!p||x.product===p)&&(!q||`${x.center_id} ${x.blood_group}`.toLowerCase().includes(q))).sort((a,b)=>Number(a.expires_sim_min)-Number(b.expires_sim_min));if(!rows.length){$('inventoryTable').innerHTML='<div class="empty-state">موردی برای نمایش وجود ندارد.</div>';return}$('inventoryTable').innerHTML=`<table><thead><tr><th>مرکز</th><th>فرآورده</th><th>گروه خونی</th><th>واحد</th><th>تاریخ انقضا</th><th>زمان شبیه‌سازی</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${safe(x.center_id)}</td><td>${safe(productLabel(x.product))}</td><td><span class="blood">${safe(x.blood_group)}</span></td><td><b>${x.units}</b></td><td dir="ltr">${safe(x.expires_at)}</td><td>${Number(x.expires_sim_min).toLocaleString('fa-IR')}</td></tr>`).join('')}</tbody></table>`}
async function loadHealth(){try{const d=await api('/health');$('apiState').className='api-state online';$('apiState').querySelector('span').textContent=`سرویس فعال · زمان شبیه‌سازی ${Number(d.sim_time).toFixed(1)}`}catch(e){$('apiState').className='api-state offline';$('apiState').querySelector('span').textContent='سرویس API در دسترس نیست'}}
async function refreshAll(){await loadHealth();try{await loadMeta();await loadRequests()}catch(e){toast('خطا در دریافت درخواست‌ها: '+e.message)}try{await loadInventory()}catch(e){$('inventoryTable').innerHTML=`<div class="empty-state">${safe(e.message)}؛ سرویس Inventory را اجرا کنید.</div>`}}
function navigate(view){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${view}`));document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.view===view));const titles={overview:'نمای کلی شبکه',hospital:'ثبت درخواست بیمارستان',requests:'پیگیری درخواست‌ها',reviews:'بررسی و تأیید درخواست‌ها',inventory:'موجودی مراکز',donor:'پرتال اهداکننده'};$('pageTitle').textContent=titles[view]||'BloodNet';if(view==='requests')loadRequests();if(view==='reviews')loadReviewQueue();if(view==='inventory')loadInventory().catch(e=>toast(e.message))}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.view)));document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.go)));
$('refreshBtn').addEventListener('click',()=>refreshAll().then(()=>toast('اطلاعات بروزرسانی شد')));
$('requestForm').addEventListener('submit',async e=>{e.preventDefault();const btn=$('submitRequest');btn.disabled=true;btn.textContent='در حال ثبت…';const body={hospital_id:$('hospitalId').value,product:$('product').value,blood_group:$('bloodGroup').value,units:Number($('units').value),urgency:$('urgency').value,note:$('note').value};try{const d=await api('/requests',{method:'POST',headers:{Authorization:`Bearer ${TOKENS.hospital}`,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(body)});showMessage('createMessage',`درخواست با شناسه ${d.request_id} ثبت شد. وضعیت: ${fa.status[d.status]||d.status}`,'success');toast('درخواست ثبت شد');await loadRequests();navigate('requests');await loadDetail(d.request_id)}catch(err){showMessage('createMessage',err.message,'error')}finally{btn.disabled=false;btn.textContent='ثبت درخواست و شروع تأمین'}});
async function loadDetail(id){try{const [r,e]=await Promise.all([api('/requests/'+encodeURIComponent(id),{headers:{Authorization:`Bearer ${TOKENS.hospital}`}}),api('/requests/'+encodeURIComponent(id)+'/events',{headers:{Authorization:`Bearer ${TOKENS.hospital}`}})]);$('requestDetail').classList.remove('hidden');$('detailTitle').textContent=`درخواست ${r.request_id}`;$('detailSub').textContent=`${hospitalName(r.hospital_id)} · ${productLabel(r.product)} · ${r.blood_group}`;$('detailStats').innerHTML=[['موردنیاز',r.needed],['تأیید دعوت',r.confirmed],['در مسیر',r.en_route],['موجودی در راه',r.stock_inflight],['تأمین واقعی',r.fulfilled]].map(x=>`<div class="detail-stat"><small>${x[0]}</small><b>${Number(x[1]).toLocaleString('fa-IR')}</b></div>`).join('');$('detailEvents').innerHTML=(e.items||[]).slice().reverse().map(x=>`<div class="timeline-item"><b>${safe(x.type)}</b><small>زمان شبیه‌سازی: ${Number(x.sim_time||0).toFixed(2)} · ${safe(x.donor_id||'')}</small></div>`).join('')||'<div class="empty-state">رویدادی ثبت نشده است.</div>';$('requestDetail').scrollIntoView({behavior:'smooth',block:'start'})}catch(err){toast(err.message)}}
async function loadReviewQueue(){
  const target=$('reviewQueue');target.innerHTML='<div class="empty-state">در حال دریافت…</div>';
  try{
    const d=await api('/requests',{headers:{Authorization:`Bearer ${TOKENS.coordinator}`}});
    const pending=(d.items||[]).filter(x=>x.status==='pending_review');
    $('reviewSummary').innerHTML=`<span class="review-count">${pending.length.toLocaleString('fa-IR')}</span><span>درخواست در انتظار تصمیم هماهنگ‌کننده</span>`;
    if(!pending.length){target.innerHTML='<div class="empty-state">در حال حاضر درخواست نیازمند بررسی وجود ندارد.</div>';return}
    target.innerHTML=`<table><thead><tr><th>شناسه</th><th>بیمارستان</th><th>فرآورده</th><th>گروه خونی</th><th>واحد</th><th>فوریت</th><th>وضعیت</th><th>اقدام</th></tr></thead><tbody>${pending.map(r=>`<tr><td><b dir="ltr">${safe(r.request_id)}</b></td><td>${safe(hospitalName(r.hospital_id))}</td><td>${safe(productLabel(r.product))}</td><td><span class="blood">${safe(r.blood_group)}</span></td><td><b>${Number(r.needed).toLocaleString('fa-IR')}</b></td><td>${safe(fa.urgency[r.urgency]||r.urgency)}</td><td>${statusBadge(r.status)}</td><td><button class="btn btn-primary btn-small" data-review="${safe(r.request_id)}">بررسی درخواست</button></td></tr>`).join('')}</tbody></table>`;
    target.querySelectorAll('[data-review]').forEach(b=>b.addEventListener('click',()=>openReview(b.dataset.review)));
  }catch(e){target.innerHTML=`<div class="message error">${safe(e.message)}</div>`}
}
async function openReview(id){
  try{
    const headers={Authorization:`Bearer ${TOKENS.coordinator}`};
    const [r,e]=await Promise.all([api('/requests/'+encodeURIComponent(id),{headers}),api('/requests/'+encodeURIComponent(id)+'/events',{headers})]);
    state.reviewRequestId=id;$('reviewTitle').textContent=`بررسی درخواست ${r.request_id}`;$('reviewSub').textContent=`${hospitalName(r.hospital_id)} · ${productLabel(r.product)} · ${r.blood_group}`;
    const facts=[['تعداد واحد',r.needed],['فوریت',fa.urgency[r.urgency]||r.urgency],['تأمین‌شده',r.fulfilled],['موجودی در راه',r.stock_inflight||0],['وضعیت',fa.status[r.status]||r.status]];
    $('reviewFacts').innerHTML=facts.map(x=>`<div class="review-fact"><small>${safe(x[0])}</small><b>${safe(x[1])}</b></div>`).join('');
    $('reviewEvents').innerHTML=(e.items||[]).slice().reverse().map(x=>`<div class="timeline-item"><b>${safe(x.type)}${x.note?` · ${safe(x.note)}`:''}</b><small>زمان شبیه‌سازی: ${Number(x.sim_time||0).toFixed(2)}</small></div>`).join('')||'<div class="empty-state">رویدادی ثبت نشده است.</div>';
    $('reviewNote').value='';$('reviewMessage').classList.add('hidden');const pending=r.status==='pending_review';$('approveRequest').disabled=!pending;$('rejectRequest').disabled=!pending;$('reviewDetail').classList.remove('hidden');$('reviewDetail').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){toast('خطا در دریافت جزئیات: '+e.message)}
}
async function decideReview(approved){
  const id=state.reviewRequestId,note=$('reviewNote').value.trim();
  if(!id){toast('ابتدا یک درخواست را انتخاب کنید');return}
  if(!approved&&!note){showMessage('reviewMessage','برای رد درخواست، ثبت دلیل الزامی است.','error');$('reviewNote').focus();return}
  const btn=approved?$('approveRequest'):$('rejectRequest');btn.disabled=true;let completed=false;
  try{
    const d=await api(`/requests/${encodeURIComponent(id)}/approve`,{method:'POST',headers:{Authorization:`Bearer ${TOKENS.coordinator}`},body:JSON.stringify({approved,note})});
    completed=true;showMessage('reviewMessage',approved?'درخواست تأیید شد و وارد فرآیند تأمین شد.':'درخواست رد شد؛ دلیل تصمیم در تاریخچه ثبت شد.','success');toast(approved?'درخواست تأیید شد':'درخواست رد شد');
    await loadReviewQueue();await loadRequests();await openReview(id);
  }catch(e){showMessage('reviewMessage',e.message,'error')}
  finally{if(completed){$('approveRequest').disabled=true;$('rejectRequest').disabled=true}else{btn.disabled=false}}
}
$('refreshReviews').addEventListener('click',loadReviewQueue);$('closeReview').addEventListener('click',()=>$('reviewDetail').classList.add('hidden'));
$('approveRequest').addEventListener('click',()=>decideReview(true));$('rejectRequest').addEventListener('click',()=>decideReview(false));
$('closeDetail').addEventListener('click',()=>$('requestDetail').classList.add('hidden'));
$('inventorySearch').addEventListener('input',renderInventory);$('inventoryProduct').addEventListener('change',renderInventory);
$('donorLookup').addEventListener('submit',async e=>{e.preventDefault();state.donorId=$('donorId').value.trim();state.donorToken=$('donorToken').value;try{const d=await api(`/donors/${encodeURIComponent(state.donorId)}/invitations`,{headers:{Authorization:`Bearer ${state.donorToken}`}});renderInvitations(d.items||[]);if(!d.items?.length)toast('برای این اهداکننده دعوتی ثبت نشده است')}catch(err){$('donorInvitations').innerHTML=`<div class="message error">${safe(err.message)}</div>`}});
function renderInvitations(items){if(!items.length){$('donorInvitations').innerHTML='<div class="empty-state">دعوتی برای این شناسه وجود ندارد.</div>';return}$('donorInvitations').innerHTML=items.map(x=>`<article class="invite-card"><strong>${safe(x.request_id)} · ${safe(productLabel(x.product))} · ${safe(x.blood_group)}</strong><p>بیمارستان ${safe(x.hospital_id)} · فوریت ${safe(fa.urgency[x.urgency])} · وضعیت دعوت: ${safe(fa.donor[x.invitation_state]||x.invitation_state)}</p><div class="invite-actions">${x.invitation_state==='notified'?`<button class="btn btn-primary" data-response="accepted" data-rid="${safe(x.request_id)}">پذیرش دعوت</button><button class="btn" data-response="declined" data-rid="${safe(x.request_id)}">رد دعوت</button>`:''}${({accepted:['en_route','no_show'],en_route:['arrived','no_show'],arrived:['screen_pass','screen_fail','no_show'],screen_pass:['donated'],screen_fail:[],no_show:[],donated:[],declined:[],stopped:[]}[x.invitation_state]||[]).map(ev=>`<button class="btn" data-progress="${ev}" data-rid="${safe(x.request_id)}">${safe(fa.donor[ev])}</button>`).join('')}</div></article>`).join('');$('donorInvitations').querySelectorAll('[data-response]').forEach(b=>b.addEventListener('click',()=>donorAction('/demo/donor-response',{request_id:b.dataset.rid,donor_id:state.donorId,response:b.dataset.response})));$('donorInvitations').querySelectorAll('[data-progress]').forEach(b=>b.addEventListener('click',()=>donorAction('/demo/donor-progress',{request_id:b.dataset.rid,donor_id:state.donorId,event:b.dataset.progress})));}
async function donorAction(path,body){try{await api(path,{method:'POST',headers:{Authorization:`Bearer ${state.donorToken}`},body:JSON.stringify(body)});toast('رویداد ثبت شد');$('donorLookup').requestSubmit()}catch(e){toast(e.message)}}
refreshAll();
