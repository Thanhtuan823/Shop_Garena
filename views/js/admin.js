'use strict';
  document.querySelectorAll('[data-ai]').forEach(button=>button.onclick=async()=>{
    checkRole();button.disabled=true;try{renderResult('operation-output',await api(button.dataset.ai,button.dataset.method||'POST'));await refreshStock();}finally{button.disabled=false;}
  });
  $('ai1-card').onclick=()=>{$('ocr-file').closest('details').open=true;$('ocr-file').scrollIntoView({behavior:'smooth'});$('ocr-file').focus();};
  $('ai4-card').onclick=()=>showDialog('admin-chat-dialog');
  $('ai6-card').onclick=()=>showDialog('admin-reconcile-dialog');
  $('ai8-card').onclick=()=>{$('dispute-form').scrollIntoView({behavior:'smooth'});$('dispute-form').elements.ma_nick.focus();};
  $('admin-chat-form').onsubmit=async event=>{event.preventDefault();renderResult('admin-chat-output',await api('/api/chat/nl2sql','POST',{prompt:$('admin-chat-prompt').value}));};
  $('admin-reconcile-form').onsubmit=async event=>{event.preventDefault();renderResult('admin-reconcile-output',await api('/api/staff/ai6-reconcile-assistant','POST',{prompt:$('admin-reconcile-prompt').value}));};
  $('fraud-button').onclick=async()=>{
    const id=$('nick-form').elements.ma_nick.value;if(!id)throw new Error('Chọn nick trong form trước');if(!await confirmAction('Khóa tranh chấp nick '+id+'?'))return;
    renderResult('operation-output',await api('/api/admin/lock-fraud/'+encodeURIComponent(id),'POST'));await refreshStock();
  };
  $('vacuum-button').onclick=async()=>{renderResult('operation-output',await api('/api/admin/run-vacuum','POST',{table:'tai_khoan_game'}));};
  $('dispute-form').onsubmit=async event=>{
    event.preventDefault();const form=event.target;renderResult('operation-output',await api('/api/admin/ai8-evaluate-dispute','POST',{ma_nick:form.elements.ma_nick.value,evidence_count:Number(form.elements.evidence_count.value),seller_unresponsive:form.elements.seller_unresponsive.checked,recovery_changed:form.elements.recovery_changed.checked}));
  };
