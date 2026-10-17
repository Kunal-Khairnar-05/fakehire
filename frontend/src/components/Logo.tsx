import logoDark from "../assets/logo-dark.png";
import logo from "../assets/logo.png";

// <picture> lets the browser pick the white-text logo when the system is in dark mode
export default function Logo({ height = 34 }: { height?: number }) {
  return (
    <picture>
      <source srcSet={logoDark} media="(prefers-color-scheme: dark)" />
      <img src={logo} alt="FakeHire" height={height} style={{ height, width: "auto", display: "block" }} />
    </picture>
  );
}
