import { useState, useEffect } from 'react';
import Materials from './routes/Materials';
import Tags from './routes/Tags';
import Jobs from './routes/Jobs';
import Questions from './routes/Questions';
import Synthesis from './routes/Synthesis';
import Experiments from './routes/Experiments';
import { api } from './api/client';

type Tab = 'materials' | 'tags' | 'questions' | 'synthesis' | 'experiments' | 'jobs';

// spec §5.4: /materials 勾选的素材可在 /synthesis 批量提炼
let _selectedMaterialIds: Set<number> = new Set();
const _listeners: (() => void)[] = [];
export function getSelectedMaterialIds(): number[] {
  return [..._selectedMaterialIds];
}
export function toggleMaterialSelection(id: number) {
  if (_selectedMaterialIds.has(id)) _selectedMaterialIds.delete(id);
  else _selectedMaterialIds.add(id);
  _listeners.forEach(fn => fn());
}
export function clearMaterialSelection() {
  _selectedMaterialIds.clear();
  _listeners.forEach(fn => fn());
}
export function onSelectionChange(fn: () => void) {
  _listeners.push(fn);
  return () => { const i = _listeners.indexOf(fn); if (i >= 0) _listeners.splice(i, 1); };
}

let _selectedAssetIds: Set<number> = new Set();
const _assetListeners: (() => void)[] = [];
export function getSelectedAssetIds(): number[] {
  return [..._selectedAssetIds];
}
export function toggleAssetSelection(id: number) {
  if (_selectedAssetIds.has(id)) _selectedAssetIds.delete(id);
  else _selectedAssetIds.add(id);
  _assetListeners.forEach(fn => fn());
}
export function clearAssetSelection() {
  _selectedAssetIds.clear();
  _assetListeners.forEach(fn => fn());
}
export function onAssetSelectionChange(fn: () => void) {
  _assetListeners.push(fn);
  return () => {
    const i = _assetListeners.indexOf(fn);
    if (i >= 0) _assetListeners.splice(i, 1);
  };
}

const TABS: { key: Tab; label: string }[] = [
  { key: 'materials', label: '素材库' },
  { key: 'tags', label: '标签体系' },
  { key: 'questions', label: '问题池' },
  { key: 'synthesis', label: '合成库' },
  { key: 'experiments', label: '内容实验' },
  { key: 'jobs', label: '任务中心' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('materials');
  useEffect(() => { api.initPort(); }, []);

  // spec §5.4: 来源素材链接点击跳 /materials/<id>
  const [pendingMaterialId, setPendingMaterialId] = useState<number | null>(null);
  const navigateToMaterial = (id: number) => {
    setPendingMaterialId(id);
    setTab('materials');
  };

  return (
    <div style={{ fontFamily: 'system-ui', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ borderBottom: '1px solid #ddd', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 4 }}>
        <strong style={{ marginRight: 24, fontSize: 15 }}>新疆定制游获客工作台</strong>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{
              padding: '4px 12px', border: 'none', borderRadius: 4, cursor: 'pointer',
              background: tab === t.key ? '#2563eb' : 'transparent',
              color: tab === t.key ? '#fff' : '#333',
              fontWeight: tab === t.key ? 600 : 400, fontSize: 14,
            }}>
            {t.label}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {tab === 'materials' ? (
          <Materials key={pendingMaterialId ?? 'm'} pendingMaterialId={pendingMaterialId}
            onConsumed={() => setPendingMaterialId(null)} />
        ) : tab === 'tags' ? <Tags /> :
          tab === 'questions' ? <Questions onNavigateToMaterial={navigateToMaterial} /> :
          tab === 'jobs' ? <Jobs /> :
          tab === 'experiments' ? <Experiments /> :
          <Synthesis onNavigateToMaterial={navigateToMaterial}
            onCreateExperiment={() => setTab('experiments')} />}
      </div>
    </div>
  );
}
