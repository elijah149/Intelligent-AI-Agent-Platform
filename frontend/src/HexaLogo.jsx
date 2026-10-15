
import "./HexaLogo.css";
import hexaLogo from "./assets/hexa-logo.svg";

export default function HexaLogo({ compact = false }) {
  return (
    <div className={`hexa-brand ${compact ? "hexa-brand--compact" : ""}`}>
      <img className="hexa-brand__icon" src={hexaLogo} alt="" />
      {!compact && (
        <div className="hexa-brand__text">
          <span className="hexa-brand__name">AI Agent Platform</span>
          <span className="hexa-brand__tagline">Intelligent Support</span>
        </div>
      )}
    </div>
  );
}
