import {useEffect,useState} from "react";
import {Plus,Trash2,RefreshCw} from "lucide-react";

const blankExpense={description:"",merchant_name:"",amount:"",currency_code:"INR",expense_date:new Date().toISOString().slice(0,10),category:"Uncategorized",payment_method:"",notes:""};
const blankVendor={name:"",default_category:"",tax_identifier:"",notes:""};
const blankBudget={name:"",category:"",amount:"",currency_code:"INR",period:"monthly",starts_on:new Date().toISOString().slice(0,10)};

export default function FinanceWorkspace({section,api}){
 const [items,setItems]=useState([]),[form,setForm]=useState(blankExpense),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const [vendor,setVendor]=useState(blankVendor),[budget,setBudget]=useState(blankBudget);
 async function load(){const endpoint=section==="Expenses"?"/expenses":section==="Vendors"?"/vendors":"/budgets";const response=await fetch(api+endpoint);const data=await response.json();setItems(data.items||[])}
 useEffect(()=>{load().catch(e=>setError(e.message))},[section]);
 async function submit(event){event.preventDefault();setBusy(true);setError("");try{const endpoint=section==="Expenses"?"/expenses":section==="Vendors"?"/vendors":"/budgets";const payload=section==="Expenses"?form:section==="Vendors"?vendor:budget;const response=await fetch(api+endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.detail||"Could not save record");setForm(blankExpense);setVendor(blankVendor);setBudget(blankBudget);await load()}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function remove(id){if(!window.confirm("Delete this record?"))return;const response=await fetch(api+"/expenses/"+id,{method:"DELETE"});if(!response.ok){setError("Could not delete this expense.");return}await load()}
 const fields=section==="Expenses"?[
  ["description","Description","text",true],["merchant_name","Merchant","text",false],["amount","Amount","number",true],["currency_code","Currency (ISO code)","text",true],["expense_date","Expense date","date",false],["category","Category","text",false],["payment_method","Payment method","text",false],["notes","Notes","text",false]
 ]:section==="Vendors"?[
  ["name","Vendor name","text",true],["default_category","Default category","text",false],["tax_identifier","Tax identifier","text",false],["notes","Notes","text",false]
 ]:[
  ["name","Budget name","text",true],["category","Category (optional)","text",false],["amount","Budget amount","number",true],["currency_code","Currency (ISO code)","text",true],["starts_on","Start date","date",false]
 ];
 const current=section==="Expenses"?form:section==="Vendors"?vendor:budget;
 const update=section==="Expenses"?setForm:section==="Vendors"?setVendor:setBudget;
 return <section className="finance-workspace">
  <div className="finance-heading"><div><h2>{section}</h2><p>{section==="Expenses"?"Record cash expenses and out-of-pocket purchases.":section==="Vendors"?"Maintain a reusable supplier directory.":"Set spending limits by currency and period."}</p></div><button className="secondary" onClick={()=>load()}><RefreshCw size={14}/> Refresh</button></div>
  <form className="finance-form" onSubmit={submit}>
   <div className="finance-fields">{fields.map(([key,label,type,required])=><label key={key}>{label}<input type={type} required={required} step={type==="number"?"0.01":undefined} value={current[key]||""} onChange={e=>update(old=>({...old,[key]:e.target.value}))}/></label>)}
   {section==="Budgets"&&<label>Period<select value={budget.period} onChange={e=>setBudget(v=>({...v,period:e.target.value}))}><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="yearly">Yearly</option></select></label>}
   </div><button className="primary" disabled={busy}><Plus size={15}/>{busy?"Saving…":"Add "+(section==="Expenses"?"expense":section==="Vendors"?"vendor":"budget")}</button>
   {error&&<p className="finance-error">{error}</p>}
  </form>
  <div className="finance-list">{items.length===0?<p className="no-tax">Nothing here yet. Add your first {section.toLowerCase().replace(/s$/,"")} above.</p>:items.map(item=><article className="finance-row" key={item.expense_id||item.vendor_id||item.budget_id}><div><b>{item.description||item.name}</b><small>{item.merchant_name||item.category||item.default_category||item.period||item.expense_date||""}</small></div><strong>{item.amount?item.currency_code+" "+item.amount:item.tax_identifier||""}</strong>{section==="Expenses"&&<button className="icon-button" title="Delete expense" onClick={()=>remove(item.expense_id)}><Trash2 size={15}/></button>}</article>)}</div>
 </section>
}
