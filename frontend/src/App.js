import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import axios from "axios";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./components/ui/dialog";
import { Badge } from "./components/ui/badge";
import { Users, BookOpen, CreditCard, Plus, Edit2, Trash2, UserCheck, Calendar, ChevronDown, ChevronRight, Download, BarChart3, LogOut, Shield } from "lucide-react";
import { useToast } from "./hooks/use-toast";
import { Toaster } from "./components/ui/toaster";
import { ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Tooltip, XAxis, YAxis, CartesianGrid, AreaChart, Area } from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function roleLabel(role) {
  const labels = { admin: "Yönetici", teacher: "Öğretmen", student: "Öğrenci", parent: "Veli" };
  return labels[role] || role;
}

function UserManagement({ teachers }) {
  const { toast } = useToast();
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ ad: "", soyad: "", email: "", password: "", role: "teacher", linked_id: "" });
  const [loading, setLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    try { const res = await axios.get(`${API}/auth/users`); setUsers(res.data); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const createUser = async (e) => {
    e.preventDefault(); setLoading(true);
    try {
      await axios.post(`${API}/auth/users`, form);
      setForm({ ad: "", soyad: "", email: "", password: "", role: "teacher", linked_id: "" });
      fetchUsers();
      toast({ title: "Başarılı", description: "Kullanıcı oluşturuldu" });
    } catch (error) {
      toast({ title: "Hata", description: error.response?.data?.detail || "Hata oluştu", variant: "destructive" });
    }
    setLoading(false);
  };

  const deleteUser = async (id) => {
    try { await axios.delete(`${API}/auth/users/${id}`); fetchUsers(); toast({ title: "Başarılı", description: "Kullanıcı silindi" }); }
    catch (error) { toast({ title: "Hata", description: error.response?.data?.detail || "Hata oluştu", variant: "destructive" }); }
  };

  const roleBadgeColor = { admin: "bg-red-100 text-red-700", teacher: "bg-blue-100 text-blue-700", student: "bg-green-100 text-green-700", parent: "bg-purple-100 text-purple-700" };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-1 border-0 shadow-sm">
        <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Kullanıcı</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={createUser} className="space-y-4">
            <div><Label>Ad</Label><Input value={form.ad} onChange={e => setForm({...form, ad: e.target.value})} required /></div>
            <div><Label>Soyad</Label><Input value={form.soyad} onChange={e => setForm({...form, soyad: e.target.value})} required /></div>
            <div><Label>E-posta</Label><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required /></div>
            <div><Label>Şifre</Label><Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={6} /></div>
            <div><Label>Rol</Label>
              <Select value={form.role} onValueChange={v => setForm({...form, role: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Yönetici</SelectItem>
                  <SelectItem value="teacher">Öğretmen</SelectItem>
                  <SelectItem value="student">Öğrenci</SelectItem>
                  <SelectItem value="parent">Veli</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={loading} className="w-full">Oluştur</Button>
          </form>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2 border-0 shadow-sm">
        <CardHeader><CardTitle>Kullanıcılar</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>E-posta</TableHead><TableHead>Rol</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
            <TableBody>
              {users.map(u => (
                <TableRow key={u.id}>
                  <TableCell>{u.ad} {u.soyad}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell><span className={`px-2 py-1 rounded-full text-xs font-medium ${roleBadgeColor[u.role] || 'bg-gray-100'}`}>{roleLabel(u.role)}</span></TableCell>
                  <TableCell><Button variant="destructive" size="sm" onClick={() => deleteUser(u.id)}><Trash2 className="h-4 w-4" /></Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function SimpleEditForm({ item, teachers, courses, classes, onSave, onCancel }) {
  const [data, setData] = useState(item.data);
  const handleSubmit = (e) => {
    e.preventDefault();
    const changed = {};
    Object.keys(data).forEach(k => { if (data[k] !== item.data[k]) changed[k] = data[k]; });
    onSave(changed);
  };
  return (
    <form onSubmit={handleSubmit} className="space-y-3 max-h-96 overflow-y-auto">
      <div><Label>Ad</Label><Input value={data.ad||''} onChange={e => setData({...data,ad:e.target.value})} /></div>
      <div><Label>Soyad</Label><Input value={data.soyad||''} onChange={e => setData({...data,soyad:e.target.value})} /></div>
      {item.type === 'teacher' && <>
        <div><Label>Branş</Label><Input value={data.brans||''} onChange={e => setData({...data,brans:e.target.value})} /></div>
        <div><Label>Telefon</Label><Input value={data.telefon||''} onChange={e => setData({...data,telefon:e.target.value})} /></div>
      </>}
      {item.type === 'student' && <>
        <div><Label>Sınıf</Label>
          <Select value={data.sinif} onValueChange={v => setData({...data,sinif:v})}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{classes.map(c=><SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div><Label>Veli Adı</Label><Input value={data.veli_ad||''} onChange={e => setData({...data,veli_ad:e.target.value})} /></div>
        <div><Label>Kur</Label><Input value={data.kur||''} onChange={e => setData({...data,kur:e.target.value})} /></div>
        <div><Label>Öğretmen</Label>
          <Select value={data.ogretmen_id||''} onValueChange={v => setData({...data,ogretmen_id:v})}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{teachers.map(t=><SelectItem key={t.id} value={t.id}>{t.ad} {t.soyad}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </>}
      {item.type === 'course' && <>
        <div><Label>Fiyat (₺)</Label><Input type="number" value={data.fiyat||0} onChange={e => setData({...data,fiyat:parseFloat(e.target.value)||0})} /></div>
        <div><Label>Süre (Saat)</Label><Input type="number" value={data.sure||0} onChange={e => setData({...data,sure:parseInt(e.target.value)||0})} /></div>
      </>}
      <div className="flex gap-2 pt-2">
        <Button type="submit" className="flex-1">Kaydet</Button>
        <Button type="button" variant="outline" onClick={onCancel} className="flex-1">İptal</Button>
      </div>
    </form>
  );
}

function AppContent() {
  // ── TÜM HOOK'LAR EN ÜSTTE ──
  const { user, logout, loading } = useAuth();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("dashboard");
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [courses, setCourses] = useState([]);
  const [payments, setPayments] = useState([]);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [weeklyStats, setWeeklyStats] = useState([]);
  const [monthlyStats, setMonthlyStats] = useState([]);
  const [teacherStudents, setTeacherStudents] = useState({});
  const [expandedTeachers, setExpandedTeachers] = useState(new Set());
  const [loadingAction, setLoadingAction] = useState(false);
  const [teacherForm, setTeacherForm] = useState({ ad: "", soyad: "", brans: "", telefon: "", seviye: "yeni", yapilmasi_gereken_odeme: 0 });
  const [studentForm, setStudentForm] = useState({ ad: "", soyad: "", sinif: "", veli_ad: "", veli_soyad: "", veli_telefon: "", aldigi_egitim: "", kur: "", yapilmasi_gereken_odeme: 0, ogretmene_yapilacak_odeme: 0, ogretmen_id: "" });
  const [courseForm, setCourseForm] = useState({ ad: "", fiyat: 0, sure: 0 });
  const [paymentForm, setPaymentForm] = useState({ tip: "ogrenci", kisi_id: "", miktar: 0, aciklama: "" });
  const [editingItem, setEditingItem] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  const availableCourses = ["Okuma Becerileri Temel", "Okuma Becerileri İleri", "Hızlı Okuma", "Anlama Becerileri", "Yazım Kuralları", "Dikkat Geliştirme", "Kelime Dağarcığı", "Metin Analizi"];
  const availableClasses = ["1-A","1-B","1-C","2-A","2-B","2-C","3-A","3-B","3-C","4-A","4-B","4-C","5-A","5-B","5-C","6-A","6-B","6-C","7-A","7-B","7-C","8-A","8-B","8-C"];

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/stats/weekly`); setWeeklyStats(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/stats/monthly`); setMonthlyStats(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/teachers`); setTeachers(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/students`); setStudents(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/courses`); setCourses(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/payments`); setPayments(r.data); } catch(e) {}
  }, []);

  useEffect(() => {
    if (user) fetchAll();
  }, [user, fetchAll]);

  // ── KOŞULLU RETURN'LER HOOK'LARDAN SONRA ──
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-16 h-16 bg-gradient-to-br from-orange-400 to-red-500 rounded-2xl flex items-center justify-center">
          <BookOpen className="h-8 w-8 text-white" />
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  const fetchTeachers = async () => { try { const r = await axios.get(`${API}/teachers`); setTeachers(r.data); } catch(e) {} };
  const fetchStudents = async () => { try { const r = await axios.get(`${API}/students`); setStudents(r.data); } catch(e) {} };
  const fetchCourses = async () => { try { const r = await axios.get(`${API}/courses`); setCourses(r.data); } catch(e) {} };
  const fetchPayments = async () => { try { const r = await axios.get(`${API}/payments`); setPayments(r.data); } catch(e) {} };
  const fetchDashboard = async () => { try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {} };
  const fetchTeacherStudents = async (id) => { try { const r = await axios.get(`${API}/teachers/${id}/students`); setTeacherStudents(p => ({...p, [id]: r.data})); } catch(e) {} };

  const toggleTeacherExpansion = (id) => {
    const next = new Set(expandedTeachers);
    if (next.has(id)) { next.delete(id); } else { next.add(id); if (!teacherStudents[id]) fetchTeacherStudents(id); }
    setExpandedTeachers(next);
  };

  const formatCurrency = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(v);
  const formatDate = (d) => new Date(d).toLocaleDateString('tr-TR');

  const handleEdit = async (updatedData) => {
    try {
      if (editingItem.type === 'teacher') { await axios.put(`${API}/teachers/${editingItem.data.id}`, updatedData); fetchTeachers(); toast({ title: "Başarılı", description: "Güncellendi" }); }
      else if (editingItem.type === 'student') { await axios.put(`${API}/students/${editingItem.data.id}`, updatedData); fetchStudents(); fetchTeachers(); setTeacherStudents({}); toast({ title: "Başarılı", description: "Güncellendi" }); }
      else if (editingItem.type === 'course') { await axios.put(`${API}/courses/${editingItem.data.id}`, updatedData); fetchCourses(); toast({ title: "Başarılı", description: "Güncellendi" }); }
      fetchDashboard(); setEditDialogOpen(false); setEditingItem(null);
    } catch { toast({ title: "Hata", description: "Güncelleme hatası", variant: "destructive" }); }
  };

  const createTeacher = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/teachers`, teacherForm); setTeacherForm({ ad:"",soyad:"",brans:"",telefon:"",seviye:"yeni",yapilmasi_gereken_odeme:0 }); fetchTeachers(); fetchDashboard(); toast({ title:"Başarılı", description:"Öğretmen eklendi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const createStudent = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/students`, studentForm); setStudentForm({ ad:"",soyad:"",sinif:"",veli_ad:"",veli_soyad:"",veli_telefon:"",aldigi_egitim:"",kur:"",yapilmasi_gereken_odeme:0,ogretmene_yapilacak_odeme:0,ogretmen_id:"" }); fetchStudents(); fetchTeachers(); fetchDashboard(); setTeacherStudents({}); toast({ title:"Başarılı", description:"Öğrenci eklendi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const createCourse = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/courses`, courseForm); setCourseForm({ ad:"",fiyat:0,sure:0 }); fetchCourses(); fetchDashboard(); toast({ title:"Başarılı", description:"Kurs eklendi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const createPayment = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/payments`, paymentForm); setPaymentForm({ tip:"ogrenci",kisi_id:"",miktar:0,aciklama:"" }); fetchPayments(); fetchTeachers(); fetchStudents(); fetchDashboard(); toast({ title:"Başarılı", description:"Ödeme kaydedildi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const deleteTeacher = async (id) => { try { await axios.delete(`${API}/teachers/${id}`); fetchTeachers(); fetchDashboard(); setTeacherStudents(p => { const n={...p}; delete n[id]; return n; }); toast({ title:"Başarılı", description:"Silindi" }); } catch { toast({ title:"Hata", variant:"destructive" }); } };
  const deleteStudent = async (id) => { try { await axios.delete(`${API}/students/${id}`); fetchStudents(); fetchTeachers(); fetchDashboard(); setTeacherStudents({}); toast({ title:"Başarılı", description:"Silindi" }); } catch { toast({ title:"Hata", variant:"destructive" }); } };
  const deleteCourse = async (id) => { try { await axios.delete(`${API}/courses/${id}`); fetchCourses(); fetchDashboard(); toast({ title:"Başarılı", description:"Silindi" }); } catch { toast({ title:"Hata", variant:"destructive" }); } };

  const exportToExcel = async () => {
    setLoadingAction(true);
    try {
      const r = await axios.get(`${API}/export`); const d = r.data;
      const wb = XLSX.utils.book_new();
      if (d.ogretmenler?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.ogretmenler), "Öğretmenler");
      if (d.ogrenciler?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.ogrenciler), "Öğrenciler");
      if (d.kurslar?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.kurslar), "Kurslar");
      if (d.odemeler?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.odemeler), "Ödemeler");
      const buf = XLSX.write(wb, { bookType:'xlsx', type:'array' });
      saveAs(new Blob([buf], { type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), `OBA_${new Date().toISOString().slice(0,10)}.xlsx`);
      toast({ title:"Başarılı", description:"Excel indirildi" });
    } catch { toast({ title:"Hata", description:"Export hatası", variant:"destructive" }); }
    setLoadingAction(false);
  };

  const pieData = dashboardStats ? [
    { name:'Öğrenci Alacakları', value:dashboardStats.toplam_ogrenci_alacak, color:'#059669' },
    { name:'Öğretmen Borçları', value:dashboardStats.toplam_ogretmen_borc, color:'#dc2626' }
  ] : [];

  const tabClass = "inline-flex items-center justify-center whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium transition-all data-[state=active]:bg-gradient-to-r data-[state=active]:from-orange-500 data-[state=active]:to-red-500 data-[state=active]:text-white data-[state=active]:shadow-sm";

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-4">
        {/* Header */}
        <div className="bg-white rounded-3xl shadow-sm p-6 mb-6 border border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-14 h-14 bg-gradient-to-br from-orange-400 to-red-500 rounded-2xl flex items-center justify-center">
                <BookOpen className="h-7 w-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Okuma Becerileri Akademisi</h1>
                <p className="text-gray-500 text-sm">Eğitim Yönetim Sistemi</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right hidden sm:block">
                <div className="text-sm font-medium text-gray-900">{user.ad} {user.soyad}</div>
                <div className="text-xs text-gray-500">{roleLabel(user.role)}</div>
              </div>
              <Button onClick={exportToExcel} disabled={loadingAction} className="bg-green-600 hover:bg-green-700 text-white"><Download className="h-4 w-4 mr-2" />Excel</Button>
              <Button variant="outline" size="sm" onClick={logout} className="flex items-center gap-2"><LogOut className="h-4 w-4" />Çıkış</Button>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="inline-flex h-12 items-center justify-center rounded-2xl bg-white p-1 shadow-sm border border-gray-200 flex-wrap gap-1 mb-6">
            <TabsTrigger value="dashboard" className={tabClass}><BarChart3 className="h-4 w-4 mr-2" />Dashboard</TabsTrigger>
            <TabsTrigger value="teachers" className={tabClass}><UserCheck className="h-4 w-4 mr-2" />Öğretmenler</TabsTrigger>
            <TabsTrigger value="students" className={tabClass}><Users className="h-4 w-4 mr-2" />Öğrenciler</TabsTrigger>
            <TabsTrigger value="courses" className={tabClass}><BookOpen className="h-4 w-4 mr-2" />Kurslar</TabsTrigger>
            <TabsTrigger value="payments" className={tabClass}><CreditCard className="h-4 w-4 mr-2" />Ödemeler</TabsTrigger>
            {user.role === "admin" && <TabsTrigger value="users" className={tabClass}><Shield className="h-4 w-4 mr-2" />Kullanıcılar</TabsTrigger>}
          </TabsList>

          {/* Dashboard */}
          <TabsContent value="dashboard">
            {dashboardStats && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-blue-50 to-blue-100 cursor-pointer" onClick={() => setActiveTab("teachers")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-blue-600">Öğretmen</p><p className="text-3xl font-bold text-blue-900">{dashboardStats.toplam_ogretmen}</p></div><div className="w-12 h-12 bg-blue-500 rounded-2xl flex items-center justify-center"><UserCheck className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-green-50 to-green-100 cursor-pointer" onClick={() => setActiveTab("students")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-green-600">Öğrenci</p><p className="text-3xl font-bold text-green-900">{dashboardStats.toplam_ogrenci}</p></div><div className="w-12 h-12 bg-green-500 rounded-2xl flex items-center justify-center"><Users className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-orange-50 to-orange-100 cursor-pointer" onClick={() => setActiveTab("courses")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-orange-600">Kurs</p><p className="text-3xl font-bold text-orange-900">{dashboardStats.toplam_kurs}</p></div><div className="w-12 h-12 bg-orange-500 rounded-2xl flex items-center justify-center"><BookOpen className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-purple-50 to-purple-100 cursor-pointer" onClick={() => setActiveTab("payments")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-purple-600">Bu Ay</p><p className="text-xl font-bold text-purple-900">{formatCurrency(dashboardStats.bu_ay_odenen_toplam)}</p></div><div className="w-12 h-12 bg-purple-500 rounded-2xl flex items-center justify-center"><Calendar className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="border-0 shadow-sm">
                    <CardHeader><CardTitle>Finansal Durum</CardTitle></CardHeader>
                    <CardContent><div className="h-64"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value">{pieData.map((e,i) => <Cell key={i} fill={e.color} />)}</Pie><Tooltip formatter={v => formatCurrency(v)} /></PieChart></ResponsiveContainer></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm">
                    <CardHeader><CardTitle>Aylık İstatistikler</CardTitle></CardHeader>
                    <CardContent><div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={monthlyStats}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="ay" /><YAxis /><Tooltip /><Bar dataKey="yeni_ogrenciler" fill="#3b82f6" /><Bar dataKey="gelir" fill="#f97316" /></BarChart></ResponsiveContainer></div></CardContent>
                  </Card>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Teachers */}
          <TabsContent value="teachers">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Öğretmen</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createTeacher} className="space-y-4">
                    <div><Label>Ad</Label><Input value={teacherForm.ad} onChange={e => setTeacherForm({...teacherForm, ad:e.target.value})} required /></div>
                    <div><Label>Soyad</Label><Input value={teacherForm.soyad} onChange={e => setTeacherForm({...teacherForm, soyad:e.target.value})} required /></div>
                    <div><Label>Branş</Label><Input value={teacherForm.brans} onChange={e => setTeacherForm({...teacherForm, brans:e.target.value})} required /></div>
                    <div><Label>Telefon</Label><Input value={teacherForm.telefon} onChange={e => setTeacherForm({...teacherForm, telefon:e.target.value})} required /></div>
                    <div><Label>Seviye</Label>
                      <Select value={teacherForm.seviye} onValueChange={v => setTeacherForm({...teacherForm, seviye:v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="yeni">Yeni</SelectItem><SelectItem value="uzman">Uzman</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div><Label>Ödeme (₺)</Label><Input type="number" step="0.01" value={teacherForm.yapilmasi_gereken_odeme} onChange={e => setTeacherForm({...teacherForm, yapilmasi_gereken_odeme:parseFloat(e.target.value)||0})} /></div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle>Öğretmenler</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {teachers.map(t => (
                      <div key={t.id} className="border border-gray-100 rounded-2xl overflow-hidden">
                        <div className="p-4 cursor-pointer hover:bg-gray-50 flex items-center justify-between" onClick={() => toggleTeacherExpansion(t.id)}>
                          <div className="flex items-center gap-4">
                            {expandedTeachers.has(t.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            <div><div className="font-medium">{t.ad} {t.soyad}</div><div className="text-sm text-gray-500">{t.brans} • {t.seviye}</div></div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-center"><div className="text-sm font-medium">{t.ogrenci_sayisi}</div><div className="text-xs text-gray-500">Öğrenci</div></div>
                            <div className="flex gap-2">
                              <Button variant="outline" size="sm" onClick={e => { e.stopPropagation(); setEditingItem({type:'teacher',data:t}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button>
                              <Button variant="destructive" size="sm" onClick={e => { e.stopPropagation(); deleteTeacher(t.id); }}><Trash2 className="h-4 w-4" /></Button>
                            </div>
                          </div>
                        </div>
                        {expandedTeachers.has(t.id) && (
                          <div className="border-t border-gray-100 bg-gray-50 p-4">
                            {teacherStudents[t.id] ? teacherStudents[t.id].map(s => (
                              <div key={s.id} className="bg-white p-3 rounded-xl border border-gray-100 mb-2">
                                <div className="font-medium text-sm">{s.ad} {s.soyad}</div>
                                <div className="text-xs text-gray-500">Kur: {s.kur} • Sınıf: {s.sinif}</div>
                              </div>
                            )) : <p className="text-sm text-gray-500">Yükleniyor...</p>}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Students */}
          <TabsContent value="students">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Öğrenci</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createStudent} className="space-y-4">
                    <div><Label>Ad</Label><Input value={studentForm.ad} onChange={e => setStudentForm({...studentForm, ad:e.target.value})} required /></div>
                    <div><Label>Soyad</Label><Input value={studentForm.soyad} onChange={e => setStudentForm({...studentForm, soyad:e.target.value})} required /></div>
                    <div><Label>Sınıf</Label>
                      <Select value={studentForm.sinif} onValueChange={v => setStudentForm({...studentForm, sinif:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{availableClasses.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Veli Adı</Label><Input value={studentForm.veli_ad} onChange={e => setStudentForm({...studentForm, veli_ad:e.target.value})} required /></div>
                    <div><Label>Veli Soyadı</Label><Input value={studentForm.veli_soyad} onChange={e => setStudentForm({...studentForm, veli_soyad:e.target.value})} required /></div>
                    <div><Label>Veli Telefon</Label><Input value={studentForm.veli_telefon} onChange={e => setStudentForm({...studentForm, veli_telefon:e.target.value})} required /></div>
                    <div><Label>Eğitim</Label>
                      <Select value={studentForm.aldigi_egitim} onValueChange={v => setStudentForm({...studentForm, aldigi_egitim:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{availableCourses.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Kur</Label><Input value={studentForm.kur} onChange={e => setStudentForm({...studentForm, kur:e.target.value})} required /></div>
                    <div><Label>Ödeme (₺)</Label><Input type="number" step="0.01" value={studentForm.yapilmasi_gereken_odeme} onChange={e => setStudentForm({...studentForm, yapilmasi_gereken_odeme:parseFloat(e.target.value)||0})} /></div>
                    <div><Label>Öğretmen Payı (₺)</Label><Input type="number" step="0.01" value={studentForm.ogretmene_yapilacak_odeme} onChange={e => setStudentForm({...studentForm, ogretmene_yapilacak_odeme:parseFloat(e.target.value)||0})} /></div>
                    <div><Label>Öğretmen</Label>
                      <Select value={studentForm.ogretmen_id} onValueChange={v => setStudentForm({...studentForm, ogretmen_id:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{teachers.map(t => <SelectItem key={t.id} value={t.id}>{t.ad} {t.soyad}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle>Öğrenciler</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>Sınıf</TableHead><TableHead>Veli</TableHead><TableHead>Öğretmen</TableHead><TableHead>Borç</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {students.map(s => {
                        const t = teachers.find(t => t.id === s.ogretmen_id);
                        return (
                          <TableRow key={s.id}>
                            <TableCell className="font-medium">{s.ad} {s.soyad}</TableCell>
                            <TableCell>{s.sinif}</TableCell>
                            <TableCell>{s.veli_ad} {s.veli_soyad}</TableCell>
                            <TableCell>{t ? `${t.ad} ${t.soyad}` : '-'}</TableCell>
                            <TableCell className="text-green-600 font-semibold">{formatCurrency(Math.max(0, s.yapilmasi_gereken_odeme - s.yapilan_odeme))}</TableCell>
                            <TableCell><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => { setEditingItem({type:'student',data:s}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button><Button variant="destructive" size="sm" onClick={() => deleteStudent(s.id)}><Trash2 className="h-4 w-4" /></Button></div></TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Courses */}
          <TabsContent value="courses">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Kurs</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createCourse} className="space-y-4">
                    <div><Label>Kurs Adı</Label><Input value={courseForm.ad} onChange={e => setCourseForm({...courseForm, ad:e.target.value})} required /></div>
                    <div><Label>Fiyat (₺)</Label><Input type="number" step="0.01" value={courseForm.fiyat} onChange={e => setCourseForm({...courseForm, fiyat:parseFloat(e.target.value)||0})} required /></div>
                    <div><Label>Süre (Saat)</Label><Input type="number" value={courseForm.sure} onChange={e => setCourseForm({...courseForm, sure:parseInt(e.target.value)||0})} required /></div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle>Kurslar</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Kurs Adı</TableHead><TableHead>Fiyat</TableHead><TableHead>Süre</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {courses.map(c => (
                        <TableRow key={c.id}>
                          <TableCell className="font-medium">{c.ad}</TableCell>
                          <TableCell>{formatCurrency(c.fiyat)}</TableCell>
                          <TableCell>{c.sure} saat</TableCell>
                          <TableCell><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => { setEditingItem({type:'course',data:c}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button><Button variant="destructive" size="sm" onClick={() => deleteCourse(c.id)}><Trash2 className="h-4 w-4" /></Button></div></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Payments */}
          <TabsContent value="payments">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Ödeme</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createPayment} className="space-y-4">
                    <div><Label>Tip</Label>
                      <Select value={paymentForm.tip} onValueChange={v => setPaymentForm({...paymentForm, tip:v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="ogrenci">Öğrenci</SelectItem><SelectItem value="ogretmen">Öğretmen</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div><Label>{paymentForm.tip === 'ogrenci' ? 'Öğrenci' : 'Öğretmen'}</Label>
                      <Select value={paymentForm.kisi_id} onValueChange={v => setPaymentForm({...paymentForm, kisi_id:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{(paymentForm.tip === 'ogrenci' ? students : teachers).map(p => <SelectItem key={p.id} value={p.id}>{p.ad} {p.soyad}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Miktar (₺)</Label><Input type="number" step="0.01" value={paymentForm.miktar} onChange={e => setPaymentForm({...paymentForm, miktar:parseFloat(e.target.value)||0})} required /></div>
                    <div><Label>Açıklama</Label><Input value={paymentForm.aciklama} onChange={e => setPaymentForm({...paymentForm, aciklama:e.target.value})} /></div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle>Ödemeler</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Tarih</TableHead><TableHead>Tip</TableHead><TableHead>Kişi</TableHead><TableHead>Miktar</TableHead><TableHead>Açıklama</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {payments.map(p => {
                        const person = p.tip === 'ogrenci' ? students.find(s => s.id === p.kisi_id) : teachers.find(t => t.id === p.kisi_id);
                        return (
                          <TableRow key={p.id}>
                            <TableCell>{formatDate(p.tarih)}</TableCell>
                            <TableCell><Badge variant={p.tip === 'ogrenci' ? 'default' : 'secondary'}>{p.tip === 'ogrenci' ? 'Öğrenci' : 'Öğretmen'}</Badge></TableCell>
                            <TableCell>{person ? `${person.ad} ${person.soyad}` : '-'}</TableCell>
                            <TableCell className="font-semibold text-green-600">{formatCurrency(p.miktar)}</TableCell>
                            <TableCell>{p.aciklama || '-'}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Users - admin only */}
          {user.role === "admin" && (
            <TabsContent value="users">
              <UserManagement teachers={teachers} />
            </TabsContent>
          )}
        </Tabs>

        {/* Edit Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{editingItem?.type === 'teacher' ? 'Öğretmen Düzenle' : editingItem?.type === 'student' ? 'Öğrenci Düzenle' : 'Kurs Düzenle'}</DialogTitle>
              <DialogDescription>Bilgileri güncelleyin</DialogDescription>
            </DialogHeader>
            {editingItem && <SimpleEditForm item={editingItem} teachers={teachers} courses={availableCourses} classes={availableClasses} onSave={handleEdit} onCancel={() => setEditDialogOpen(false)} />}
          </DialogContent>
        </Dialog>
      </div>
      <Toaster />
    </div>
  );
}

export default function App() {
  return <AppContent />;
}
