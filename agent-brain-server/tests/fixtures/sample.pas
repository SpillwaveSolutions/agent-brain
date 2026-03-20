{ Agent Brain - Sample Object Pascal unit for AST chunking tests }

unit SampleUnit;

interface

uses
  SysUtils;

const
  MAX_ITEMS = 100;
  DEFAULT_COLOR = 'red';

type
  TDirection = (dNorth, dSouth, dEast, dWest);

  TPoint = record
    X: Integer;
    Y: Integer;
  end;

  TShape = class
  private
    FColor: string;
    FVisible: Boolean;
  public
    constructor Create(const AColor: string);
    destructor Destroy; override;
    procedure SetColor(const AColor: string);
    function GetColor: string;
    function IsVisible: Boolean;
    procedure Draw; virtual;
  end;

  TCircle = class(TShape)
  private
    FRadius: Double;
  public
    constructor Create(const AColor: string; ARadius: Double);
    function GetArea: Double;
    procedure Draw; override;
  end;

function CalculateDistance(const A, B: TPoint): Double;
procedure PrintPoint(const P: TPoint);

implementation

uses
  Math;

{ TShape implementation }

constructor TShape.Create(const AColor: string);
begin
  FColor := AColor;
  FVisible := True;
end;

destructor TShape.Destroy;
begin
  inherited Destroy;
end;

procedure TShape.SetColor(const AColor: string);
begin
  FColor := AColor;
end;

function TShape.GetColor: string;
begin
  Result := FColor;
end;

function TShape.IsVisible: Boolean;
begin
  Result := FVisible;
end;

procedure TShape.Draw;
begin
  WriteLn('Drawing shape with color: ', FColor);
end;

{ TCircle implementation }

constructor TCircle.Create(const AColor: string; ARadius: Double);
begin
  inherited Create(AColor);
  FRadius := ARadius;
end;

function TCircle.GetArea: Double;
begin
  Result := Pi * FRadius * FRadius;
end;

procedure TCircle.Draw;
begin
  WriteLn('Drawing circle with radius: ', FRadius:0:2);
end;

{ Standalone routines }

function CalculateDistance(const A, B: TPoint): Double;
var
  DX, DY: Double;
begin
  DX := B.X - A.X;
  DY := B.Y - A.Y;
  Result := Sqrt(DX * DX + DY * DY);
end;

procedure PrintPoint(const P: TPoint);
begin
  WriteLn(Format('Point(%d, %d)', [P.X, P.Y]));
end;

end.
