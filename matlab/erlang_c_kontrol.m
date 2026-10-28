% FENG 497 - Erlang C capraz kontrolu (Python cekirdegi ile ayni vakalar)
% Calistirma: MATLAB'de bu klasore gelip  erlang_c_kontrol  yazin.
% Beklenen: C(2,1) = 0.3333 ; lambda=8, mu=5, c=2 -> Wq = 21.33 dk, P(W<=30 dk) = 0.738

function erlang_c_kontrol()
    fprintf('C(2,1)            = %.4f  (beklenen 0.3333)\n', erlangC(2, 1));
    [Wq, P] = bekleme(8, 5, 2, 0.5);
    fprintf('Wq (8,5,2)        = %.2f dk (beklenen 21.33)\n', Wq * 60);
    fprintf('P(W <= 30 dk)     = %.3f   (beklenen 0.738)\n', P);
    % Gereken hekim: %90 hasta 30 dk icinde
    for c = 1:10
        [~, P] = bekleme(8, 5, c, 0.5);
        if P >= 0.90
            fprintf('Gereken hekim     = %d (lambda=8, mu=5, hedef %%90 / 30 dk)\n', c);
            break
        end
    end
end

function C = erlangC(c, a)
    if a >= c, C = 1; return; end
    B = 1;
    for k = 1:c
        B = a * B / (k + a * B);   % Erlang B ozyinelemesi
    end
    C = c * B / (c - a * (1 - B));
end

function [Wq, P] = bekleme(lambda, mu, c, t)
    a = lambda / mu;
    if a >= c, Wq = Inf; P = 0; return; end
    C = erlangC(c, a);
    Wq = C / (c * mu - lambda);                 % saat
    P = 1 - C * exp(-(c * mu - lambda) * t);    % P(W <= t)
end
