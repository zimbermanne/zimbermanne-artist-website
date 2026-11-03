import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getToken, login as apiLogin, me, setToken } from "./api";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(!getToken());

  useEffect(() => {
    if (getToken()) me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
    const out = () => setUser(null);
    window.addEventListener("zimbermanne:signed-out", out);
    return () => window.removeEventListener("zimbermanne:signed-out", out);
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await apiLogin(email, password);
    setToken(res.access_token);
    setUser({ email: res.email });
  }, []);
  const logout = useCallback(() => { setToken(null); setUser(null); }, []);

  return <AuthCtx.Provider value={{ user, ready, login, logout }}>{children}</AuthCtx.Provider>;
}
