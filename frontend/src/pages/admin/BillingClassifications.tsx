import React, { useState, useEffect } from 'react';
import {
  listBillingClassifications,
  createBillingClassification,
  updateBillingClassification,
  deleteBillingClassification,
  matchBillingClassification
} from '../../api/client';
import { PlusCircle, Search, Edit2, Trash2, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import Topbar from '../../components/Topbar';
import Card from '../../components/Card';

export function BillingClassifications() {
  const [classifications, setClassifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    category: '',
    description: '',
    item_type: 'SERVICE',
    hsn_sac_code: '',
    hsn_sac_type: 'SAC',
    gst_rate: 18.0,
    keywords: '',
    active: true
  });

  // Test match state
  const [testText, setTestText] = useState('');
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    fetchClassifications();
  }, []);

  const fetchClassifications = async () => {
    try {
      setLoading(true);
      const data = await listBillingClassifications();
      setClassifications(data);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load classifications');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!testText.trim()) return;
    try {
      setTesting(true);
      const res = await matchBillingClassification(testText);
      if (res && res.length > 0) {
        setTestResult(res[0]);
      } else {
        setTestResult({ error: 'No matches found' });
      }
    } catch (err: any) {
      toast.error(err.message || 'Test failed');
    } finally {
      setTesting(false);
    }
  };

  const openCreateModal = () => {
    setEditingId(null);
    setFormData({
      category: '',
      description: '',
      item_type: 'SERVICE',
      hsn_sac_code: '',
      hsn_sac_type: 'SAC',
      gst_rate: 18.0,
      keywords: '',
      active: true
    });
    setShowModal(true);
  };

  const openEditModal = (c: any) => {
    setEditingId(c.id);
    setFormData({
      category: c.category,
      description: c.description,
      item_type: c.item_type,
      hsn_sac_code: c.hsn_sac_code,
      hsn_sac_type: c.hsn_sac_type,
      gst_rate: parseFloat(c.gst_rate),
      keywords: c.keywords || '',
      active: c.active
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await updateBillingClassification(editingId, formData);
        toast.success('Classification updated');
      } else {
        await createBillingClassification(formData);
        toast.success('Classification created');
      }
      setShowModal(false);
      fetchClassifications();
    } catch (err: any) {
      toast.error(err.message || 'Save failed');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to disable this classification?')) return;
    try {
      await deleteBillingClassification(id);
      toast.success('Disabled successfully');
      fetchClassifications();
    } catch (err: any) {
      toast.error(err.message || 'Delete failed');
    }
  };

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar
        showBack
        title="Billing Classifications"
        subtitle="Catalog of billable items (HSN/SAC) used to auto-classify invoice line items."
      >
        <button
          onClick={openCreateModal}
          className="text-sm font-medium bg-brand-600 text-white px-4 py-2.5 rounded-full hover:bg-brand-700 inline-flex items-center gap-2 transition-colors"
        >
          <PlusCircle className="w-4 h-4" />
          Add Classification
        </button>
      </Topbar>

      <div className="p-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Test Tool Panel */}
          <Card className="lg:col-span-1 h-fit">
            <h2 className="font-semibold text-slate-800 flex items-center gap-2 mb-1">
              <Search className="w-4 h-4 text-brand-600" />
              Test Classifier Engine
            </h2>
            <p className="text-sm text-slate-500 mb-4">
              Enter a free-text billing description below to see how the system auto-classifies it.
            </p>
            <textarea
              className="w-full border border-slate-200 rounded-2xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300 resize-none"
              rows={3}
              placeholder="e.g. 'Annual cloud hosting and maintenance'"
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
            />
            <button
              onClick={handleTest}
              disabled={testing || !testText.trim()}
              className="w-full mt-3 bg-slate-900 text-white py-2.5 rounded-full text-sm font-medium disabled:opacity-50 hover:bg-slate-800 transition-colors"
            >
              {testing ? 'Testing…' : 'Test Match'}
            </button>

            {testResult && !testResult.error && (
              <div className="mt-4 p-4 bg-brand-50 rounded-2xl border border-brand-100 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-brand-700 uppercase tracking-wide">Match Found</span>
                  <span className="bg-brand-100 text-brand-800 text-xs px-2.5 py-1 rounded-full font-semibold">
                    Score: {testResult.score}
                  </span>
                </div>
                <p className="font-medium text-slate-900">{testResult.description}</p>
                <div className="flex gap-4 text-sm mt-2">
                  <div><span className="text-slate-500">Code:</span> <span className="font-semibold text-slate-800">{testResult.hsn_sac_code}</span></div>
                  <div><span className="text-slate-500">GST:</span> <span className="font-semibold text-slate-800">{testResult.gst_rate}%</span></div>
                </div>
                <div className="text-xs text-slate-400 mt-2 truncate">
                  Keywords: {testResult.keywords || 'None'}
                </div>
              </div>
            )}
            {testResult?.error && (
              <div className="mt-4 p-4 bg-coral-50 rounded-2xl border border-coral-100 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-coral-500 shrink-0" />
                <span className="text-sm text-coral-700">No confident match found.</span>
              </div>
            )}
          </Card>

          {/* Catalog Table */}
          <Card className="lg:col-span-2 !p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-slate-50 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="px-5 py-3 font-medium">Category / Description</th>
                    <th className="px-5 py-3 font-medium">HSN/SAC</th>
                    <th className="px-5 py-3 font-medium text-right">GST %</th>
                    <th className="px-5 py-3 font-medium text-center">Status</th>
                    <th className="px-5 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400">Loading…</td></tr>
                  ) : classifications.length === 0 ? (
                    <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400">No classifications found</td></tr>
                  ) : (
                    classifications.map((c) => (
                      <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="font-medium text-slate-800">{c.category}</div>
                          <div className="text-slate-400 text-xs truncate max-w-[300px]">{c.description}</div>
                        </td>
                        <td className="px-5 py-3.5 font-mono text-slate-600">{c.hsn_sac_code} <span className="text-xs text-slate-400">({c.hsn_sac_type})</span></td>
                        <td className="px-5 py-3.5 text-right font-medium text-slate-700">{parseFloat(c.gst_rate)}%</td>
                        <td className="px-5 py-3.5 text-center">
                          {c.active ?
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 bg-brand-50 px-2.5 py-1 rounded-full"><CheckCircle className="w-3 h-3" /> Active</span> :
                            <span className="inline-flex items-center gap-1 text-xs font-medium text-coral-600 bg-coral-50 px-2.5 py-1 rounded-full"><XCircle className="w-3 h-3" /> Disabled</span>
                          }
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button onClick={() => openEditModal(c)} className="text-slate-400 hover:text-brand-600 p-1.5 rounded-full hover:bg-brand-50 transition-colors"><Edit2 className="w-4 h-4" /></button>
                          {c.active && (
                            <button onClick={() => handleDelete(c.id)} className="text-slate-400 hover:text-coral-600 p-1.5 rounded-full hover:bg-coral-50 ml-1 transition-colors"><Trash2 className="w-4 h-4" /></button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-[2px] p-4">
          <div className="bg-white rounded-3xl shadow-card w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900 mb-4">{editingId ? 'Edit Classification' : 'New Classification'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Category</label>
                  <input required type="text" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.category} onChange={(e) => setFormData({...formData, category: e.target.value})} placeholder="e.g. Software Development" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Item Type</label>
                  <select className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.item_type} onChange={(e) => setFormData({...formData, item_type: e.target.value})}>
                    <option value="SERVICE">Service</option>
                    <option value="HARDWARE">Hardware</option>
                    <option value="SOFTWARE">Software License</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Description (Internal / Display Name)</label>
                <input required type="text" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} placeholder="e.g. Custom backend development services" />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Type</label>
                  <select className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.hsn_sac_type} onChange={(e) => setFormData({...formData, hsn_sac_type: e.target.value})}>
                    <option value="SAC">SAC</option>
                    <option value="HSN">HSN</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">HSN/SAC Code</label>
                  <input required type="text" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.hsn_sac_code} onChange={(e) => setFormData({...formData, hsn_sac_code: e.target.value})} placeholder="e.g. 998314" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">GST Rate (%)</label>
                  <input required type="number" step="0.1" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.gst_rate} onChange={(e) => setFormData({...formData, gst_rate: parseFloat(e.target.value)})} />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Matcher Keywords (comma separated)</label>
                <input type="text" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.keywords} onChange={(e) => setFormData({...formData, keywords: e.target.value})} placeholder="e.g. api, integration, backend, nodejs" />
                <p className="text-xs text-slate-400 mt-1">These words increase the confidence score during auto-matching.</p>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" id="active" className="rounded text-brand-600 focus:ring-brand-400" checked={formData.active} onChange={(e) => setFormData({...formData, active: e.target.checked})} />
                <span className="text-sm font-medium text-slate-700">Active (available for matching and selection)</span>
              </label>

              <div className="pt-4 flex justify-end gap-3 border-t border-slate-100">
                <button type="button" onClick={() => setShowModal(false)} className="px-5 py-2.5 rounded-full text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">Cancel</button>
                <button type="submit" className="px-5 py-2.5 rounded-full text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 transition-colors">Save Classification</button>
              </div>

            </form>
          </div>
        </div>
      )}
    </div>
  );
}
