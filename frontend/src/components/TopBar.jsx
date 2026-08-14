import { useNavigate } from 'react-router-dom';
import './TopBar.css';

export default function TopBar({ title, back = false, right = null }) {
  const navigate = useNavigate();

  return (
    <header className="topbar">
      <div className="topbar-left">
        {back ? (
          <button className="back-btn" onClick={() => navigate(-1)} aria-label="Volver">
            ‹
          </button>
        ) : (
          <span className="topbar-seal">学</span>
        )}
      </div>

      <h1 className="topbar-title">{title}</h1>

      <div className="topbar-right">{right}</div>
    </header>
  );
}
