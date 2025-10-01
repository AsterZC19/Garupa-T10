import axios from 'axios'
const api = axios.create({ baseURL: '' }) // 空意味着同源，vite dev 时会 proxy 到 backend
export default api
