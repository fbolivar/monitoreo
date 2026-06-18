import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';

/** Web Push / PWA (#11): registra el SW, suscribe el navegador y lo envía a la API. */
@Injectable({ providedIn: 'root' })
export class PushService {
  private api = inject(ApiService);

  get soportado(): boolean {
    return 'serviceWorker' in navigator && 'PushManager' in window;
  }

  async activar(): Promise<string> {
    if (!this.soportado) return 'Este navegador no soporta notificaciones push.';

    const permiso = await Notification.requestPermission();
    if (permiso !== 'granted') return 'Permiso de notificaciones denegado.';

    const reg = await navigator.serviceWorker.register('/sw.js');
    await navigator.serviceWorker.ready;

    const { publicKey } = await firstValueFrom(this.api.get<{ publicKey: string }>('/push/vapid'));
    if (!publicKey) return 'El servidor no tiene configurada la clave VAPID (push deshabilitado).';

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: this.urlB64ToUint8Array(publicKey) as BufferSource,
    });

    await firstValueFrom(this.api.post('/push/suscribir', sub.toJSON()));
    return '¡Notificaciones push activadas!';
  }

  private urlB64ToUint8Array(base64: string): Uint8Array {
    const padding = '='.repeat((4 - (base64.length % 4)) % 4);
    const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(b64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }
}
