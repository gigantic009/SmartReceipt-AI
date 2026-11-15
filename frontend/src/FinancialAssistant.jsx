import {useState} from "react";
import {Bot,Send,Sparkles} from "lucide-react";

const suggestions=["How much did I spend in INR?","Show my Travel spending","Which documents need review?","How are my budgets doing?"];

export default function FinancialAssistant({api}){
 const [question,setQuestion]=useState(""),[result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 async function ask(value=question){if(!value.trim())return;setQuestion(value);setBusy(true);setError("");try{const response=await fetch(api+"/assistant/query",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:value})});const data=await response.json();if(!response.ok)throw Error(data.detail||"Assistant request failed");setResult(data)}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <section className="assistant-workspace">
  <div className="assistant-intro"><div className="assistant-mark"><Bot size={24}/></div><div><h2>Financial assistant</h2><p>Ask questions about your saved documents, expenses, budgets and review queue. Answers are grounded in your local ledger.</p></div></div>
  <div className="suggestion-chips">{suggestions.map(item=><button key={item} onClick={()=>ask(item)}>{item}</button>)}</div>
  <form className="assistant-input" onSubmit={e=>{e.preventDefault();ask()}}><input value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask about your finances…" maxLength={1000}/><button className="primary" disabled={busy||!question.trim()}><Send size={15}/>{busy?"Thinking…":"Ask"}</button></form>
  {error&&<p className="finance-error">{error}</p>}
  {result&&<div className="assistant-answer"><div className="assistant-answer-title"><Sparkles size={16}/> Answer</div><p>{result.answer}</p><small>Query type: {result.intent?.replaceAll("_"," ")}</small>{result.evidence?.length>0&&<details><summary>View supporting records ({result.evidence.length})</summary><pre>{JSON.stringify(result.evidence,null,2)}</pre></details>}</div>}
  <p className="assistant-disclaimer">This assistant reports saved ledger data. It does not provide tax, legal or investment advice, and it cannot infer transactions that were never entered.</p>
 </section>
}
