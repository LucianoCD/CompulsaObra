import React, { useEffect, useRef, useState } from 'react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import { Lock, Mail, User, Building2, X, AlertCircle, Loader2 } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, register, switchMode } = useWorkspaceStore();
  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (isOpen && dialogRef.current) {
      if (!dialogRef.current.open) dialogRef.current.showModal();
    } else if (!isOpen && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      if (isRegister) {
        if (!fullName.trim()) {
          throw new Error('Por favor ingresa tu nombre completo.');
        }
        await register(
          email.trim(),
          password,
          fullName.trim(),
          workspaceName.trim() || undefined
        );
      } else {
        await login(email.trim(), password);
      }
      onClose();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Error de autenticación');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickSwitch = async () => {
    setFormError(null);
    setIsSubmitting(true);
    try {
      await switchMode(false);
      onClose();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Error al cambiar a cuenta real');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="auth-modal-title"
      onClose={onClose}
      className="fixed inset-0 m-auto w-full max-w-md bg-surface-elevated border border-surface-hairline rounded-container shadow-2xl p-0 text-content-primary backdrop:bg-black/50 backdrop:backdrop-blur-xs focus:outline-none"
    >
      <div className="p-6 relative">
        <button
          onClick={onClose}
          type="button"
          className="absolute top-4 right-4 text-content-muted hover:text-content-primary p-1.5 rounded-control hover:bg-surface-subtle transition"
          aria-label="Cerrar modal"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="mb-5">
          <span className="text-[10px] font-mono uppercase text-action-primary font-bold">
            CompulsaObra ID
          </span>
          <h2 id="auth-modal-title" className="text-lg font-bold text-content-primary font-display mt-0.5">
            {isRegister ? 'Crear Cuenta Real de Presupuestador' : 'Iniciar Sesión'}
          </h2>
          <p className="text-xs text-content-secondary mt-1 leading-snug">
            Accede a tu espacio de trabajo privado para computar materiales y almacenar listas comerciales reales en Jujuy.
          </p>
        </div>

        {formError && (
          <div role="alert" className="mb-4 p-3 rounded-control bg-action-danger/10 border border-action-danger/30 flex items-start gap-2.5 text-xs text-action-danger font-medium">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{formError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {isRegister && (
            <>
              <div>
                <label className="block text-xs font-semibold text-content-secondary mb-1">
                  Nombre Completo
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-content-muted absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Ej. Ing. Juan Pérez"
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 py-2 text-xs text-content-primary focus:outline-none focus:border-surface-strong"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-content-secondary mb-1">
                  Nombre de la Constructora o Estudio (Opcional)
                </label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-content-muted absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    placeholder="Ej. Pérez & Asoc. Construcciones"
                    className="w-full bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 py-2 text-xs text-content-primary focus:outline-none focus:border-surface-strong"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-semibold text-content-secondary mb-1">
              Correo Electrónico
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-content-muted absolute left-3 top-2.5" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="juan@constructora.com"
                className="w-full bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 py-2 text-xs text-content-primary focus:outline-none focus:border-surface-strong font-mono text-[11px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-content-secondary mb-1">
              Contraseña
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-content-muted absolute left-3 top-2.5" />
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 py-2 text-xs text-content-primary focus:outline-none focus:border-surface-strong"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 px-4 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-50 text-white font-bold text-xs shadow-sm transition flex items-center justify-center gap-2 min-h-[40px]"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Procesando...</span>
              </>
            ) : isRegister ? (
              'Crear Cuenta y Espacio Privado'
            ) : (
              'Iniciar Sesión'
            )}
          </button>
        </form>

        <div className="mt-4 pt-4 border-t border-surface-hairline flex flex-col gap-2">
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setFormError(null);
            }}
            className="text-xs text-content-secondary hover:text-action-primary transition text-center font-semibold"
          >
            {isRegister ? '¿Ya tienes cuenta? Inicia sesión aquí' : '¿No tienes cuenta? Regístrate gratis'}
          </button>

          <button
            type="button"
            onClick={handleQuickSwitch}
            disabled={isSubmitting}
            className="text-[11px] text-content-muted hover:text-content-secondary transition text-center underline underline-offset-2"
          >
            O cambiar a espacio real temporal anónimo
          </button>
        </div>
      </div>
    </dialog>
  );
};
