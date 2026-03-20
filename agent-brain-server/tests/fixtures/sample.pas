unit SampleShapes;

interface

uses
  SysUtils,
  Math;

type
  TPoint = record
    X: Double;
    Y: Double;
  end;

  TShape = class
  private
    FName: string;
  public
    constructor Create(const AName: string);
    function Area: Double; virtual; abstract;
    function Perimeter: Double; virtual; abstract;
    procedure Move(const DeltaX, DeltaY: Double); virtual;
    property Name: string read FName;
  end;

  TCircle = class(TShape)
  private
    FRadius: Double;
    FCenter: TPoint;
  public
    constructor Create(const AName: string; ARadius: Double);
    function Area: Double; override;
    function Perimeter: Double; override;
    procedure TCircle.SetRadius(const Value: Double);
    function TCircle.GetDiameter: Double;
  end;

  TRectangle = class(TShape)
  private
    FWidth: Double;
    FHeight: Double;
  public
    constructor Create(const AName: string; AWidth, AHeight: Double);
    function Area: Double; override;
    function Perimeter: Double; override;
    procedure Resize(const AWidth, AHeight: Double);
  end;

function ClampValue(const Value, MinValue, MaxValue: Double): Double;
procedure PrintShapeInfo(const Shape: TShape);

implementation

constructor TShape.Create(const AName: string);
begin
  FName := AName;
end;

procedure TShape.Move(const DeltaX, DeltaY: Double);
begin
  Writeln(Format('%s moved by (%f, %f)', [FName, DeltaX, DeltaY]));
end;

constructor TCircle.Create(const AName: string; ARadius: Double);
begin
  inherited Create(AName);
  FRadius := ARadius;
  FCenter.X := 0;
  FCenter.Y := 0;
end;

function TCircle.Area: Double;
begin
  Result := Pi * Sqr(FRadius);
end;

function TCircle.Perimeter: Double;
begin
  Result := 2 * Pi * FRadius;
end;

procedure TCircle.SetRadius(const Value: Double);
begin
  FRadius := ClampValue(Value, 0.1, 1000.0);
end;

function TCircle.GetDiameter: Double;
begin
  Result := FRadius * 2;
end;

constructor TRectangle.Create(const AName: string; AWidth, AHeight: Double);
begin
  inherited Create(AName);
  FWidth := AWidth;
  FHeight := AHeight;
end;

function TRectangle.Area: Double;
begin
  Result := FWidth * FHeight;
end;

function TRectangle.Perimeter: Double;
begin
  Result := 2 * (FWidth + FHeight);
end;

procedure TRectangle.Resize(const AWidth, AHeight: Double);
begin
  FWidth := AWidth;
  FHeight := AHeight;
end;

function ClampValue(const Value, MinValue, MaxValue: Double): Double;
begin
  if Value < MinValue then
    Result := MinValue
  else if Value > MaxValue then
    Result := MaxValue
  else
    Result := Value;
end;

procedure PrintShapeInfo(const Shape: TShape);
begin
  Writeln('Shape: ' + Shape.Name);
  Writeln('Area: ' + FloatToStr(Shape.Area));
  Writeln('Perimeter: ' + FloatToStr(Shape.Perimeter));
end;

end.
