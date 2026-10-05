const $=(s,e=document)=>e.querySelector(s), $$=(s,e=document)=>[...e.querySelectorAll(s)];
let deferredPrompt=null;

function money(v){
  return Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
}

async function api(url,options={}){
  const method=(options.method||'GET').toUpperCase();
  const headers={...(options.headers||{})};

  if(options.body && !headers['Content-Type']){
    headers['Content-Type']='application/json';
  }

  if(['POST','PUT','PATCH','DELETE'].includes(method)){
    headers['X-Mota-Request']='1';
  }

  const r=await fetch(url,{...options,method,headers,credentials:'same-origin'});
  let data={};

  try{data=await r.json();}catch{}

  if(!r.ok){
    if(r.status===401){
      throw new Error('Acesso não autorizado. Reabra o endereço de rede com o token.');
    }
    throw new Error(data.erro||'Erro na operação');
  }

  return data;
}

function toast(msg){
  const t=$('#toast');
  if(!t)return;
  t.textContent=msg;
  t.classList.remove('hidden');
  clearTimeout(window.__toastTimer);
  window.__toastTimer=setTimeout(()=>t.classList.add('hidden'),2800);
}

function setView(name){
  $$('.view').forEach(v=>v.classList.remove('active'));
  $$('.nav[data-view]').forEach(v=>v.classList.remove('active'));

  $('#view-'+name)?.classList.add('active');
  $(`.nav[data-view="${name}"]`)?.classList.add('active');

  const map={
    dashboard:['Dashboard','Indicadores, desempenho e alertas'],
    vendas:['Vendas & Comissões','Gerencie vendas e acompanhe comissões'],
    estoque:['Estoque','Produtos, saldos e movimentações'],
    juros:['Juros','Simulação de atraso e encargos'],
    ferramentas:['Ferramentas','Exportações, backup e utilidades'],
    sobre:['Sobre','Projeto e identificação profissional']
  };

  if(map[name]){
    $('#pageTitle').textContent=map[name][0];
    $('#pageSubtitle').textContent=map[name][1];
  }

  $('#sidebar')?.classList.remove('open');

  if(name==='vendas'){loadSales();loadCommissionChart(currentCommissionPeriod);}
  if(name==='estoque'){
    loadProducts();
    loadMoves();
  }
}

$$('.nav[data-view]').forEach(
  b=>b.addEventListener('click',()=>setView(b.dataset.view))
);

$('#menuBtn')?.addEventListener(
  'click',
  ()=>$('#sidebar')?.classList.toggle('open')
);

function toggleTheme(){
  document.body.classList.toggle('dark');
  localStorage.theme=document.body.classList.contains('dark')?'dark':'light';
}

$('#themeBtn')?.addEventListener('click',toggleTheme);
$('#themeSideBtn')?.addEventListener('click',toggleTheme);

if(localStorage.theme==='dark'){
  document.body.classList.add('dark');
}

function updateClock(){
  const d=new Date();
  if($('#clockNow'))$('#clockNow').textContent=d.toLocaleTimeString('pt-BR');
  if($('#dateNow'))$('#dateNow').textContent=d.toLocaleDateString('pt-BR');
}
updateClock();
setInterval(updateClock,1000);

function renderBars(){
  const raw=$('#dashboardData');
  const box=$('#salesBars');

  if(!raw||!box)return;

  let data=[];
  try{data=JSON.parse(raw.textContent||'[]');}catch{return;}

  const max=Math.max(...data.map(x=>Number(x[1].total)||0),1);
  box.replaceChildren();

  for(const [name,d] of data){
    const row=document.createElement('div');
    row.className='bar-row';

    const label=document.createElement('span');
    label.textContent=String(name).split(' ')[0];

    const track=document.createElement('div');
    track.className='bar-track';

    const fill=document.createElement('div');
    fill.className='bar-fill';
    fill.style.width=`${((Number(d.total)||0)/max)*100}%`;

    const value=document.createElement('small');
    value.textContent=String(Math.round(Number(d.total)||0));

    track.appendChild(fill);
    row.append(label,track,value);
    box.appendChild(row);
  }
}
renderBars();

function openModal(title){
  $('#modalTitle').textContent=title;
  $('#modalBody').replaceChildren();
  $('#modal').classList.remove('hidden');
  return $('#modalBody');
}

function closeModal(){
  $('#modal').classList.add('hidden');
  $('#modalBody').replaceChildren();
}

$('#closeModal')?.addEventListener('click',closeModal);
$('#modal')?.addEventListener(
  'click',
  e=>{if(e.target.id==='modal')closeModal();}
);

function makeButton(text,className,handler){
  const b=document.createElement('button');
  b.type='button';
  b.className=className;
  b.textContent=text;
  b.addEventListener('click',handler);
  return b;
}

function makeField(form,labelText,value=''){
  const label=document.createElement('label');
  label.textContent=labelText;

  const input=document.createElement('input');
  input.value=value??'';

  form.append(label,input);
  return input;
}

async function loadSales(){
  const rows=await api('/api/vendas');
  const q=($('#salesSearch')?.value||'').toLowerCase();
  const tbody=$('#salesTable tbody');
  if(!tbody)return;

  tbody.replaceChildren();

  rows
    .filter(r=>String(r.vendedor).toLowerCase().includes(q))
    .forEach(r=>{
      const tr=document.createElement('tr');

      const values=[
        r.id,
        r.vendedor,
        r.produto||'—',
        money(r.valor),
        `${Number(r.percentual_comissao).toLocaleString('pt-BR')}%`,
        money(r.comissao),
        r.criado_em
      ];

      for(const value of values){
        const td=document.createElement('td');
        td.textContent=String(value??'');
        tr.appendChild(td);
      }

      const actions=document.createElement('td');
      const wrap=document.createElement('div');
      wrap.className='actions';

      wrap.append(
        makeButton('Editar','ghost',()=>saleModal(r)),
        makeButton('Excluir','primary danger',()=>deleteSale(r.id))
      );

      actions.appendChild(wrap);
      tr.appendChild(actions);
      tbody.appendChild(tr);
    });
}

$('#salesSearch')?.addEventListener('input',loadSales);
$('#newSaleBtn')?.addEventListener('click',()=>saleModal());

async function saleModal(row=null){
  const body=openModal(row?'Editar venda':'Nova venda');
  const form=document.createElement('form');

  const products=await api('/api/produtos');

  const seller=makeField(form,'Vendedor',row?.vendedor||'');
  seller.maxLength=120;

  const productLabel=document.createElement('label');
  productLabel.textContent='Produto (opcional)';

  const product=document.createElement('select');
  const empty=document.createElement('option');
  empty.value='';
  empty.textContent='Sem produto / regra original do desafio';
  product.appendChild(empty);

  for(const p of products){
    const opt=document.createElement('option');
    opt.value=String(p.codigo);
    opt.textContent=`${p.codigo} - ${p.descricao}`;
    opt.dataset.price=String(p.preco_venda||0);
    opt.dataset.percent=(
      p.comissao_percentual===null
      ||p.comissao_percentual===undefined
    )?'':String(p.comissao_percentual);

    if(row?.codigo_produto===p.codigo){
      opt.selected=true;
    }

    product.appendChild(opt);
  }

  form.append(productLabel,product);

  const value=makeField(form,'Valor da venda',row?.valor??'');
  value.inputMode='decimal';

  const pct=makeField(
    form,
    'Percentual de comissão (%)',
    row?.percentual_comissao??''
  );
  pct.inputMode='decimal';
  pct.placeholder='Automático pela regra/produto';

  const hint=document.createElement('small');
  hint.textContent=(
    'Ao selecionar um produto, o percentual cadastrado nele é usado. '
    +'Você ainda pode ajustar o percentual especificamente nesta venda.'
  );
  form.appendChild(hint);

  const preview=document.createElement('div');
  preview.className='info-strip';
  form.appendChild(preview);

  const save=document.createElement('button');
  save.type='submit';
  save.className='primary full';
  save.textContent='Salvar venda';
  form.appendChild(save);

  const getNumber=value=>{
    const text=String(value??'').trim();
    if(!text)return NaN;
    return parseFloat(text.replace(/\./g,'').replace(',','.'));
  };

  const update=()=>{
    const selected=product.selectedOptions[0];

    if(selected && selected.value){
      if(!value.value && Number(selected.dataset.price)>0){
        value.value=Number(selected.dataset.price).toLocaleString(
          'pt-BR',
          {minimumFractionDigits:2,maximumFractionDigits:2}
        );
      }

      if(!pct.value && selected.dataset.percent!==''){
        pct.value=Number(selected.dataset.percent).toLocaleString('pt-BR');
      }
    }

    const v=getNumber(value.value)||0;
    let p=getNumber(pct.value);

    if(!Number.isFinite(p)){
      p=v<100?0:v<500?1:5;
    }

    const c=v*(p/100);
    preview.textContent=(
      `Comissão prevista: ${money(c)} • Percentual aplicado: `
      +`${p.toLocaleString('pt-BR')}%`
    );
  };

  product.addEventListener('change',()=>{
    const selected=product.selectedOptions[0];

    if(selected?.value){
      const price=Number(selected.dataset.price||0);
      const percent=selected.dataset.percent;

      if(price>0){
        value.value=price.toLocaleString(
          'pt-BR',
          {minimumFractionDigits:2,maximumFractionDigits:2}
        );
      }

      pct.value=percent===''?'':Number(percent).toLocaleString('pt-BR');
    }

    update();
  });

  value.addEventListener('input',update);
  pct.addEventListener('input',update);
  update();

  form.addEventListener('submit',async e=>{
    e.preventDefault();

    const parsed=getNumber(value.value);
    const pctParsed=getNumber(pct.value);

    const payload={
      vendedor:seller.value,
      valor:parsed,
      codigo_produto:product.value?Number(product.value):null,
      percentual_comissao:Number.isFinite(pctParsed)?pctParsed:null
    };

    try{
      await api(
        row?`/api/vendas/${row.id}`:'/api/vendas',
        {
          method:row?'PUT':'POST',
          body:JSON.stringify(payload)
        }
      );

      closeModal();
      await loadSales();
      toast('Venda salva com sucesso');
    }catch(err){
      alert(err.message);
    }
  });

  body.appendChild(form);
}
async function deleteSale(id){
  if(!confirm('Excluir esta venda?'))return;

  try{
    await api(`/api/vendas/${id}`,{method:'DELETE'});
    await loadSales();
    toast('Venda excluída');
  }catch(err){
    alert(err.message);
  }
}

async function loadProducts(){
  const rows=await api('/api/produtos');
  const tbody=$('#productsTable tbody');

  if(!tbody)return;
  tbody.replaceChildren();

  rows.forEach(r=>{
    const tr=document.createElement('tr');

    const status=Number(r.estoque)<=20
      ?'Crítico'
      :Number(r.estoque)<=80
        ?'Atenção'
        :'Disponível';

    const margin=(
      Number(r.preco_venda)>0
      ?Number(r.preco_venda)-Number(r.custo_unitario||0)
      :0
    );

    const commission=(
      r.comissao_percentual===null
      ||r.comissao_percentual===undefined
      ?'Regra padrão'
      :`${Number(r.comissao_percentual).toLocaleString('pt-BR')}%`
    );

    const values=[
      r.codigo,
      r.descricao,
      r.estoque,
      money(r.custo_unitario||0),
      money(r.preco_venda||0),
      money(margin),
      commission,
      status
    ];

    for(const value of values){
      const td=document.createElement('td');
      td.textContent=String(value??'');
      tr.appendChild(td);
    }

    const actions=document.createElement('td');
    const wrap=document.createElement('div');
    wrap.className='actions';

    wrap.append(
      makeButton('Editar','ghost',()=>productModal(r)),
      makeButton('Excluir','primary danger',()=>deleteProduct(r.codigo))
    );

    actions.appendChild(wrap);
    tr.appendChild(actions);
    tbody.appendChild(tr);
  });
}
async function loadMoves(){
  const rows=await api('/api/movimentacoes');
  const tbody=$('#movesTable tbody');

  if(!tbody)return;
  tbody.replaceChildren();

  rows.forEach(r=>{
    const tr=document.createElement('tr');

    for(const value of [
      r.criado_em,
      r.produto,
      r.tipo,
      r.quantidade,
      r.estoque_anterior,
      r.estoque_final,
      r.descricao||''
    ]){
      const td=document.createElement('td');
      td.textContent=String(value??'');
      tr.appendChild(td);
    }

    tbody.appendChild(tr);
  });
}

$('#newProductBtn')?.addEventListener(
  'click',
  ()=>productModal()
);

function productModal(row=null){
  const body=openModal(row?'Editar produto':'Novo produto');
  const form=document.createElement('form');

  const code=makeField(form,'Código',row?.codigo??'');
  code.inputMode='numeric';
  if(row)code.disabled=true;

  const desc=makeField(form,'Descrição',row?.descricao||'');
  desc.maxLength=200;

  let stock=null;
  if(!row){
    stock=makeField(form,'Estoque inicial','0');
    stock.inputMode='numeric';
  }

  const cost=makeField(
    form,
    'Custo unitário',
    row?.custo_unitario??'0'
  );
  cost.inputMode='decimal';

  const price=makeField(
    form,
    'Preço de venda',
    row?.preco_venda??'0'
  );
  price.inputMode='decimal';

  const pct=makeField(
    form,
    'Comissão de venda (%)',
    row?.comissao_percentual??''
  );
  pct.inputMode='decimal';
  pct.placeholder='Ex.: 3,5';

  const explanation=document.createElement('small');
  explanation.textContent=(
    'Defina este percentual considerando a margem de lucro do produto, '
    +'os custos operacionais e as práticas de mercado do setor. '
    +'Se ficar em branco, as vendas usarão a regra original do desafio.'
  );
  form.appendChild(explanation);

  const preview=document.createElement('div');
  preview.className='info-strip';
  form.appendChild(preview);

  const getNumber=value=>{
    const text=String(value??'').trim();
    if(!text)return NaN;
    return parseFloat(text.replace(/\./g,'').replace(',','.'));
  };

  const update=()=>{
    const c=getNumber(cost.value)||0;
    const p=getNumber(price.value)||0;
    const cp=getNumber(pct.value);
    const margin=p-c;
    const marginPct=p>0?(margin/p)*100:0;

    preview.textContent=(
      `Margem bruta estimada: ${money(margin)} `
      +`(${marginPct.toLocaleString('pt-BR',{maximumFractionDigits:2})}%)`
      +(Number.isFinite(cp)
        ?` • Comissão: ${cp.toLocaleString('pt-BR')}%`
        :' • Comissão: regra padrão')
    );
  };

  cost.addEventListener('input',update);
  price.addEventListener('input',update);
  pct.addEventListener('input',update);
  update();

  const save=document.createElement('button');
  save.type='submit';
  save.className='primary full';
  save.textContent='Salvar produto';
  form.appendChild(save);

  form.addEventListener('submit',async e=>{
    e.preventDefault();

    const pctParsed=getNumber(pct.value);

    const payload={
      descricao:desc.value,
      custo_unitario:getNumber(cost.value)||0,
      preco_venda:getNumber(price.value)||0,
      comissao_percentual:Number.isFinite(pctParsed)?pctParsed:null
    };

    if(!row){
      payload.codigo=Number(code.value);
      payload.estoque=Number(stock.value);
    }

    try{
      await api(
        row?`/api/produtos/${row.codigo}`:'/api/produtos',
        {
          method:row?'PUT':'POST',
          body:JSON.stringify(payload)
        }
      );

      closeModal();
      await loadProducts();
      toast('Produto salvo');
    }catch(err){
      alert(err.message);
    }
  });

  body.appendChild(form);
}
async function deleteProduct(codigo){
  if(!confirm('Excluir este produto?'))return;

  try{
    await api(`/api/produtos/${codigo}`,{method:'DELETE'});
    await loadProducts();
    toast('Produto excluído');
  }catch(err){
    alert(err.message);
  }
}

$('#newMoveBtn')?.addEventListener('click',async()=>{
  try{
    const products=await api('/api/produtos');
    const body=openModal('Nova movimentação');
    const form=document.createElement('form');

    const productLabel=document.createElement('label');
    productLabel.textContent='Produto';

    const product=document.createElement('select');

    for(const p of products){
      const option=document.createElement('option');
      option.value=String(p.codigo);
      option.dataset.stock=String(p.estoque);
      option.textContent=`${p.codigo} - ${p.descricao}`;
      product.appendChild(option);
    }

    form.append(productLabel,product);

    const stockNow=document.createElement('div');
    stockNow.className='info-strip';
    form.appendChild(stockNow);

    const typeLabel=document.createElement('label');
    typeLabel.textContent='Tipo';

    const type=document.createElement('select');

    for(const t of ['Entrada','Saída']){
      const option=document.createElement('option');
      option.value=t;
      option.textContent=t;
      type.appendChild(option);
    }

    form.append(typeLabel,type);

    const qty=makeField(form,'Quantidade','');
    qty.inputMode='numeric';

    const desc=makeField(form,'Descrição','');
    desc.maxLength=200;

    const preview=document.createElement('div');
    preview.className='info-strip';
    form.appendChild(preview);

    const save=document.createElement('button');
    save.type='submit';
    save.className='primary full';
    save.textContent='Confirmar movimentação';
    form.appendChild(save);

    const update=()=>{
      const option=product.selectedOptions[0];
      const current=Number(option?.dataset.stock||0);
      const amount=Number(qty.value||0);
      const final=type.value==='Entrada'
        ?current+amount
        :current-amount;

      stockNow.textContent=`Saldo atual: ${current}`;
      preview.textContent=final>=0
        ?`Saldo após movimentação: ${final}`
        :'Saída superior ao saldo disponível';
    };

    product.addEventListener('change',update);
    type.addEventListener('change',update);
    qty.addEventListener('input',update);
    update();

    form.addEventListener('submit',async e=>{
      e.preventDefault();

      try{
        await api('/api/movimentacoes',{
          method:'POST',
          body:JSON.stringify({
            codigo:Number(product.value),
            tipo:type.value,
            quantidade:Number(qty.value),
            descricao:desc.value
          })
        });

        closeModal();
        await loadProducts();
        await loadMoves();
        toast('Movimentação registrada');
      }catch(err){
        alert(err.message);
      }
    });

    body.appendChild(form);
  }catch(err){
    alert(err.message);
  }
});

function maskDate(el){
  let d=el.value.replace(/\D/g,'').slice(0,8);

  if(d.length>4){
    d=d.slice(0,2)+'/'+d.slice(2,4)+'/'+d.slice(4);
  }else if(d.length>2){
    d=d.slice(0,2)+'/'+d.slice(2);
  }

  el.value=d;
}

$('#dueDate')?.addEventListener('input',e=>{
  maskDate(e.target);
  autoCalc();
});

$('#interestValue')?.addEventListener('input',autoCalc);

$('#todayBtn')?.addEventListener('click',()=>{
  const d=new Date();

  $('#dueDate').value=
    String(d.getDate()).padStart(2,'0')
    +'/'
    +String(d.getMonth()+1).padStart(2,'0')
    +'/'
    +d.getFullYear();

  autoCalc();
});

$('#calcBtn')?.addEventListener(
  'click',
  ()=>calcInterest(false)
);

async function autoCalc(){
  if(
    $('#dueDate')?.value.length===10
    &&$('#interestValue')?.value
  ){
    calcInterest(true);
  }
}

async function calcInterest(silent){
  try{
    const valor=parseFloat(
      $('#interestValue')
        .value
        .replace(/\./g,'')
        .replace(',','.')
    );

    const r=await api('/api/juros',{
      method:'POST',
      body:JSON.stringify({
        valor,
        vencimento:$('#dueDate').value
      })
    });

    $('#interestStatus').textContent=r.status;
    $('#interestTotal').textContent=money(r.total);
    $('#interestDetails').textContent=
      `Valor original: ${money(valor)} • `
      +`Dias em atraso: ${r.dias} • `
      +`Juros: ${money(r.juros)} • `
      +`Hoje: ${r.hoje}`;

    $('#dateFeedback').textContent='Data válida';
    $('#dateFeedback').style.color='var(--success)';
  }catch(err){
    $('#dateFeedback').textContent='Data inválida';
    $('#dateFeedback').style.color='var(--danger)';

    if(!silent)alert(err.message);
  }
}

function updateInstallVisibility(){
  const standalone=
    window.matchMedia('(display-mode: standalone)').matches
    ||window.navigator.standalone===true;

  const buttons=[
    $('#installBtn'),
    $('#installSideBtn'),
    $('#installToolBtn')
  ].filter(Boolean);

  if(standalone){
    buttons.forEach(b=>{
      b.textContent='App instalado';
      b.disabled=true;
    });
  }
}

async function installApp(){
  if(deferredPrompt){
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt=null;
    return;
  }

  const isiOS=/iphone|ipad|ipod/i.test(navigator.userAgent);

  if(isiOS){
    alert(
      'No iPhone/iPad: Safari → Compartilhar → Adicionar à Tela de Início.'
    );
  }else{
    alert(
      'Use o menu do navegador → Instalar app / Adicionar à tela inicial. '
      +'Em celular acessado por IP local, a instalação PWA pode exigir HTTPS.'
    );
  }
}

window.addEventListener('beforeinstallprompt',e=>{
  e.preventDefault();
  deferredPrompt=e;
  updateInstallVisibility();
});

[
  $('#installBtn'),
  $('#installSideBtn'),
  $('#installToolBtn')
].filter(Boolean).forEach(
  b=>b.addEventListener('click',installApp)
);

window.addEventListener('appinstalled',()=>{
  deferredPrompt=null;
  updateInstallVisibility();
  toast('Mota Suite instalado com sucesso');
});

updateInstallVisibility();

if('serviceWorker' in navigator){
  navigator.serviceWorker
    .register('/static/sw.js')
    .catch(console.error);
}


async function showReadme(){
  const body=openModal('README do projeto');

  const loading=document.createElement('div');
  loading.className='info-strip';
  loading.textContent='Carregando documentação...';
  body.appendChild(loading);

  try{
    const result=await api('/api/readme');

    body.replaceChildren();

    const viewer=document.createElement('div');
    viewer.className='doc-viewer';
    viewer.textContent=result.content||'README vazio.';

    body.appendChild(viewer);
  }catch(err){
    loading.textContent=err.message;
  }
}

function showRoadmap(){
  const body=openModal('Possíveis evoluções do sistema');

  const intro=document.createElement('div');
  intro.className='info-strip';
  intro.textContent=(
    'Roadmap sugerido para evoluir o Mota Business Suite '
    +'sem comprometer segurança, simplicidade e manutenção.'
  );
  body.appendChild(intro);

  const roadmap=[
    {
      title:'Autenticação e perfis de acesso',
      priority:'Alta prioridade',
      text:'Login com perfis Administrador, Gestor e Vendedor, permissões por módulo e registro de sessões.'
    },
    {
      title:'Auditoria completa',
      priority:'Alta prioridade',
      text:'Registrar quem criou, editou ou excluiu vendas, produtos, comissões e movimentações.'
    },
    {
      title:'Comissão por categoria e vendedor',
      priority:'Alta prioridade',
      text:'Permitir regras por produto, categoria, vendedor, campanha e período, preservando o histórico aplicado em cada venda.'
    },
    {
      title:'Simulador de margem e comissão',
      priority:'Alta prioridade',
      text:'Sugerir uma faixa sustentável de comissão considerando custo, preço de venda, margem desejada e despesas operacionais.'
    },
    {
      title:'Dashboard financeiro avançado',
      priority:'Média prioridade',
      text:'Indicadores de faturamento, lucro bruto, custo, margem, comissões, ticket médio e evolução por período.'
    },
    {
      title:'Relatórios PDF e Excel',
      priority:'Média prioridade',
      text:'Gerar relatórios profissionais por vendedor, produto, estoque, comissão e período.'
    },
    {
      title:'Metas e campanhas comerciais',
      priority:'Média prioridade',
      text:'Cadastrar metas mensais, campanhas temporárias, bônus e acompanhamento de atingimento.'
    },
    {
      title:'Alertas inteligentes de estoque',
      priority:'Média prioridade',
      text:'Estoque mínimo por produto, previsão de ruptura e alertas para reposição.'
    },
    {
      title:'PostgreSQL e ambiente multiusuário',
      priority:'Evolução estrutural',
      text:'Migrar de SQLite para PostgreSQL quando houver acesso simultâneo de vários usuários ou hospedagem pública.'
    },
    {
      title:'API REST versionada',
      priority:'Evolução estrutural',
      text:'Separar frontend e backend para integração com aplicativo mobile, ERP, e-commerce ou outros sistemas.'
    },
    {
      title:'HTTPS e publicação em nuvem',
      priority:'Evolução estrutural',
      text:'Hospedagem segura com domínio, certificado HTTPS, backups automáticos e PWA instalável também em celulares.'
    },
    {
      title:'Aplicativo mobile dedicado',
      priority:'Futuro',
      text:'Empacotar a experiência para Android/iOS ou criar cliente mobile consumindo a API do sistema.'
    }
  ];

  const list=document.createElement('div');
  list.className='roadmap-list';

  roadmap.forEach(item=>{
    const card=document.createElement('article');
    card.className='roadmap-item';

    const header=document.createElement('div');
    header.className='roadmap-item-header';

    const title=document.createElement('h4');
    title.textContent=item.title;

    const priority=document.createElement('span');
    priority.className='roadmap-priority';
    priority.textContent=item.priority;

    const text=document.createElement('p');
    text.textContent=item.text;

    header.append(title,priority);
    card.append(header,text);
    list.appendChild(card);
  });

  body.appendChild(list);
}

[
  $('#viewReadmeBtn'),
  $('#viewReadmeBtnCard')
].filter(Boolean).forEach(
  btn=>btn.addEventListener('click',showReadme)
);

[
  $('#viewRoadmapBtn'),
  $('#viewRoadmapBtnCard')
].filter(Boolean).forEach(
  btn=>btn.addEventListener('click',showRoadmap)
);


let currentCommissionPeriod='semana';

async function loadCommissionChart(period='semana'){
  currentCommissionPeriod=period;

  document.querySelectorAll('.period-btn').forEach(btn=>{
    btn.classList.toggle(
      'active',
      btn.dataset.period===period
    );
  });

  const chart=$('#commissionChart');
  if(!chart)return;

  chart.replaceChildren();

  const loading=document.createElement('div');
  loading.className='chart-empty';
  loading.textContent='Carregando gráfico...';
  chart.appendChild(loading);

  try{
    const result=await api(
      `/api/comissoes-resumo?periodo=${encodeURIComponent(period)}`
    );

    $('#chartPeriodLabel').textContent=result.periodo_label||'—';
    $('#chartSalesTotal').textContent=money(result.total_vendido||0);
    $('#chartCommissionTotal').textContent=money(result.total_comissao||0);
    $('#chartLeader').textContent=result.lider||'—';

    chart.replaceChildren();

    if(!result.dados || result.dados.length===0){
      const empty=document.createElement('div');
      empty.className='chart-empty';
      empty.textContent='Nenhuma venda encontrada neste período.';
      chart.appendChild(empty);
      return;
    }

    const max=Math.max(
      ...result.dados.map(item=>Number(item.comissao)||0),
      1
    );

    result.dados.forEach(item=>{
      const row=document.createElement('div');
      row.className='commission-row';

      const seller=document.createElement('div');
      seller.className='commission-seller';

      const sellerName=document.createElement('strong');
      sellerName.textContent=item.vendedor;

      const sellerInfo=document.createElement('small');
      sellerInfo.textContent=`${item.vendas} venda${item.vendas===1?'':'s'}`;

      seller.append(sellerName,sellerInfo);

      const track=document.createElement('div');
      track.className='commission-track';

      const fill=document.createElement('div');
      fill.className='commission-fill';

      const width=Math.max(
        2,
        ((Number(item.comissao)||0)/max)*100
      );

      fill.style.width=`${width}%`;
      fill.title=`${item.vendedor}: ${money(item.comissao)}`;

      track.appendChild(fill);

      const values=document.createElement('div');
      values.className='commission-values';

      const commission=document.createElement('strong');
      commission.textContent=money(item.comissao);

      const sales=document.createElement('small');
      sales.textContent=`Vendido: ${money(item.valor_vendido)}`;

      values.append(commission,sales);

      row.append(seller,track,values);
      chart.appendChild(row);
    });

  }catch(err){
    chart.replaceChildren();

    const error=document.createElement('div');
    error.className='chart-empty';
    error.textContent=`Não foi possível carregar o gráfico: ${err.message}`;
    chart.appendChild(error);
  }
}

document.querySelectorAll('.period-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    loadCommissionChart(btn.dataset.period);
  });
});

if($('#commissionChart')){
  loadCommissionChart(currentCommissionPeriod);
}
