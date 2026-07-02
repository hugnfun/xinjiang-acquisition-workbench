import { useState } from 'react';
import Materials from './routes/Materials';
import Jobs from './routes/Jobs';
import Questions from './routes/Questions';

export default function App() {
  const [tab, setTab] = useState<'materials' | 'questions' | 'jobs'>('materials');
  return (
    <div style={{ fontFamily: 'system-ui' }}>
      <div style={{ borderBottom: '1px solid #eee', padding: '8px 16px' }}>
        <strong style={{ marginRight: 24 }}>新疆定制游获客工作台</strong>
        <button onClick={() => setTab('materials')} style={{ fontWeight: tab==='materials'?700:400 }}>素材库</button>
        <button onClick={() => setTab('questions')} style={{ fontWeight: tab==='questions'?700:400, marginLeft: 8 }}>问题池</button>
        <button onClick={() => setTab('jobs')} style={{ fontWeight: tab==='jobs'?700:400, marginLeft: 8 }}>任务中心</button>
      </div>
      {tab === 'materials' ? <Materials /> : tab === 'questions' ? <Questions /> : <Jobs />}
    </div>
  );
}
