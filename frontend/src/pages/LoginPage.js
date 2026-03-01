// ─────────────────────────────────────────────────────────────
// src/pages/LoginPage.js
// ─────────────────────────────────────────────────────────────

import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { BookOpen, Eye, EyeOff } from "lucide-react";
import { useToast } from "../hooks/use-toast";

export default function LoginPage() {
  const { login } = useAuth();
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      // Başarılı login: App.js yönlendirme yapacak
    } catch (error) {
      toast({
        title: "Giriş Başarısız",
        description: error.response?.data?.detail || "E-posta veya şifre hatalı",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-red-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-orange-400 to-red-500 rounded-3xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <BookOpen className="h-10 w-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Okuma Becerileri</h1>
          <p className="text-gray-500 mt-1">Akademisi</p>
        </div>

        {/* Login Card */}
        <Card className="border-0 shadow-xl">
          <CardHeader className="pb-4">
            <CardTitle className="text-xl text-gray-900">Giriş Yap</CardTitle>
            <CardDescription>Hesabınıza erişmek için bilgilerinizi girin</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <Label htmlFor="email">E-posta</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="ornek@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="mt-1"
                />
              </div>
              
              <div>
                <Label htmlFor="password">Şifre</Label>
                <div className="relative mt-1">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white h-11 text-base font-medium"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="spinner" />
                    Giriş yapılıyor...
                  </span>
                ) : "Giriş Yap"}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Rol bilgisi */}
        <div className="mt-6 p-4 bg-white rounded-2xl border border-gray-100 shadow-sm">
          <p className="text-xs text-gray-500 text-center font-medium mb-3">Giriş sonrası yönlendirileceksiniz</p>
          <div className="grid grid-cols-2 gap-2 text-xs text-center">
            <div className="bg-blue-50 rounded-xl p-2">
              <div className="font-semibold text-blue-700">Yönetici</div>
              <div className="text-blue-500">Tam yönetim</div>
            </div>
            <div className="bg-green-50 rounded-xl p-2">
              <div className="font-semibold text-green-700">Öğretmen</div>
              <div className="text-green-500">Koçluk paneli</div>
            </div>
            <div className="bg-orange-50 rounded-xl p-2">
              <div className="font-semibold text-orange-700">Öğrenci</div>
              <div className="text-orange-500">Görev & okuma</div>
            </div>
            <div className="bg-purple-50 rounded-xl p-2">
              <div className="font-semibold text-purple-700">Veli</div>
              <div className="text-purple-500">Gelişim takibi</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
