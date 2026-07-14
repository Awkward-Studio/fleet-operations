"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  User,
  loginUser,
  registerUser,
  logoutUser,
  getCurrentUser,
  changeUserPassword
} from "./api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (payload: Record<string, string>) => Promise<void>;
  register: (payload: Record<string, string>) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (payload: Record<string, string>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const router = useRouter();

  useEffect(() => {
    async function loadUser() {
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const u = await getCurrentUser();
        setUser(u);
      } catch (err) {
        console.error("Failed to load user info on startup:", err);
        if (typeof window !== "undefined") {
          localStorage.removeItem("accessToken");
          localStorage.removeItem("refreshToken");
        }
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  async function login(payload: Record<string, string>) {
    setLoading(true);
    try {
      const data = await loginUser(payload);
      if (typeof window !== "undefined") {
        localStorage.setItem("accessToken", data.access);
        localStorage.setItem("refreshToken", data.refresh);
      }
      const u = await getCurrentUser();
      setUser(u);
      router.push("/");
    } catch (err) {
      setUser(null);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  async function register(payload: Record<string, string>) {
    setLoading(true);
    try {
      await registerUser(payload);
      // Auto-login after registration
      const loginPayload = {
        username: payload.username,
        password: payload.password
      };
      const data = await loginUser(loginPayload);
      if (typeof window !== "undefined") {
        localStorage.setItem("accessToken", data.access);
        localStorage.setItem("refreshToken", data.refresh);
      }
      const u = await getCurrentUser();
      setUser(u);
      router.push("/");
    } catch (err) {
      setUser(null);
      throw err;
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    setLoading(true);
    const refresh = typeof window !== "undefined" ? localStorage.getItem("refreshToken") : null;
    try {
      if (refresh) {
        await logoutUser({ refresh });
      }
    } catch (err) {
      console.error("Logout failed on server:", err);
    } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("accessToken");
        localStorage.removeItem("refreshToken");
      }
      setUser(null);
      setLoading(false);
      router.push("/login");
    }
  }

  async function changePassword(payload: Record<string, string>) {
    await changeUserPassword(payload);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
