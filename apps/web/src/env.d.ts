/** Build-time settings of the web app (see apps/web/README.md, "API thật"). */
interface ImportMetaEnv {
  /** "http": talk to the session API of services/api. Anything else: the in-browser mock. */
  readonly VITE_API?: string;
  /** Origin of the API when it is not behind the dev proxy, for example "http://localhost:8000". */
  readonly VITE_API_URL?: string;
}
