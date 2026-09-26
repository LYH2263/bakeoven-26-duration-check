import { useEffect, useState } from "react";
import { api } from "../api/client";
type P = { id: number; name: string; ferment_min: number; bake_min: number };
export default function ProductsPage() {
  const [rows, setRows] = useState<P[]>([]);
  const [name, setName] = useState("");
  const [ferment, setFerment] = useState(40);
  const [bake, setBake] = useState(30);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const reload = () => api<P[]>("/products").then(setRows);
  useEffect(() => { reload(); }, []);
  async function create() {
    setMsg(""); setErr("");
    try {
      const p = await api<P>("/products", { method: "POST", body: JSON.stringify({ name, ferment_min: ferment, bake_min: bake }) });
      setMsg(`已新增 ${p.name}`);
      setName("");
      reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>产品（配方时长）</h2>
    <div className="toolbar">
      <input placeholder="产品名称" value={name} onChange={e => setName(e.target.value)} />
      <label>发酵 min <input type="number" value={ferment} onChange={e => setFerment(Number(e.target.value))} style={{ width: 70 }} /></label>
      <label>烘烤 min <input type="number" value={bake} onChange={e => setBake(Number(e.target.value))} style={{ width: 70 }} /></label>
      <button onClick={create}>新增产品</button>
    </div>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>名称</th><th>发酵 min</th><th>烘烤 min</th><th>合计</th></tr></thead>
    <tbody>{rows.map(p => <tr key={p.id}><td>{p.name}</td><td className="mono">{p.ferment_min}</td><td className="mono">{p.bake_min}</td><td className="mono">{p.ferment_min + p.bake_min}</td></tr>)}</tbody></table>
  </>);
}
