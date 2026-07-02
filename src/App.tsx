import { useState, useEffect } from 'react';
import Materials from './routes/Materials';
import Jobs from './routes/Jobs';
import Questions from './routes/Questions';
import Synthesis from './routes/Synthesis';
import { api } from './api/client';

export default function App() {
  const [tab, setTab] = useState<'materials' | 'questions' | 'jobs' | 'synthesis'>('materials');
  // Resolve the sidecar port on mount (pull-based via get_sidecar_port Tauri
  // command) so getImageUrl and all fetches hit the right port.
  useEffect(() => { api.initPort(); }, []);
  return (
    <div style={{ fontFamily: 'system-ui' }}>
      <div style={{ borderBottom: '1px solid #eee', padding: '8px 16px' }}>
        <strong style={{ marginRight: 24 }}>新疆定制游获客工作台</strong>
        <button onClick={() => setTab('materials')} style={{ fontWeight: tab==='materials'?700:400 }}>素材库</button>
        <button onClick={() => setTab('questions')} style={{ fontWeight: tab==='questions'?700:400, marginLeft: 8 }}>问题池</button>
        <button onClick={() => setTab('jobs')} style={{ fontWeight: tab==='jobs'?700:400, marginLeft: 8 }}>任务中心</button>
        <button onClick={() => setTab('synthesis')} style={{ fontWeight: tab==='synthesis'?700:400, marginLeft: 8 }}>合成库</button>
      </div>
      {tab === 'materials' ? <Materials /> : tab === 'questions' ? <Questions /> : tab === 'jobs' ? <Jobs /> : <Synthesis />}
    </div>
  );
}
